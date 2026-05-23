using System.Diagnostics;
using System.IO.Pipelines;
using System.IO.Pipes;
using Microsoft.Extensions.Logging;
using TechSupport.Shared.Protocol;

namespace TechSupport.Agent.Consent;

/// <summary>
/// Spawns TechSupport.ConsentPrompt.exe in the interactive user's session
/// and asks for permission before a remote session is allowed to start.
/// Communicates with the prompt over a per-request named pipe.
///
/// In v0 we Process.Start the prompt with the current process token.
/// When the agent runs as the SYSTEM service this must be replaced with
/// CreateProcessAsUser targeting the active console session — that work
/// lives in v2 (see docs/roadmap.md).
/// </summary>
public sealed class ConsentBroker
{
    private readonly ILogger<ConsentBroker> _log;
    private readonly string _promptExecutablePath;

    public ConsentBroker(ILogger<ConsentBroker> log, string? promptExecutablePath = null)
    {
        _log = log;
        _promptExecutablePath = promptExecutablePath ?? ResolveDefaultPromptPath();
    }

    private static string ResolveDefaultPromptPath()
    {
        var dir = AppContext.BaseDirectory;
        var same = Path.Combine(dir, "TechSupport.ConsentPrompt.exe");
        if (File.Exists(same)) return same;

        var sibling = Path.Combine(dir, "..", "..", "..", "..",
            "TechSupport.ConsentPrompt", "bin", "Debug",
            "net8.0-windows10.0.19041.0", "TechSupport.ConsentPrompt.exe");
        return Path.GetFullPath(sibling);
    }

    public async Task<bool> RequestAsync(
        string technicianName,
        string reason,
        TimeSpan timeout,
        CancellationToken ct)
    {
        if (!File.Exists(_promptExecutablePath))
        {
            _log.LogWarning(
                "Consent prompt not found at {Path}; auto-denying for safety.",
                _promptExecutablePath);
            return false;
        }

        var pipeName = $"TechSupport.Consent.{Guid.NewGuid():N}";

        await using var server = new NamedPipeServerStream(
            pipeName,
            PipeDirection.InOut,
            maxNumberOfServerInstances: 1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous);

        using var process = StartPromptProcess(pipeName);
        if (process is null) return false;

        using var connectCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        connectCts.CancelAfter(TimeSpan.FromSeconds(5));
        try
        {
            await server.WaitForConnectionAsync(connectCts.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            _log.LogWarning("Consent prompt failed to connect within 5s; auto-denying.");
            try { process.Kill(); } catch { /* best effort */ }
            return false;
        }

        var prompt = new ConsentPromptMessage(technicianName, reason, (int)timeout.TotalSeconds);
        await FrameCodec.WriteAsync(
            server, MessageType.ConsentPrompt, JsonMessages.Encode(prompt), ct).ConfigureAwait(false);

        var reader = PipeReader.Create(server);
        using var replyCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        replyCts.CancelAfter(timeout + TimeSpan.FromSeconds(5));

        try
        {
            var (type, _) = await FrameCodec.ReadAsync(reader, replyCts.Token).ConfigureAwait(false);
            return type == MessageType.ConsentGranted;
        }
        catch (OperationCanceledException)
        {
            _log.LogInformation("Consent prompt timed out; treating as deny.");
            return false;
        }
    }

    private Process? StartPromptProcess(string pipeName)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = _promptExecutablePath,
                Arguments = pipeName,
                UseShellExecute = false,
            };
            return Process.Start(psi);
        }
        catch (Exception ex)
        {
            _log.LogError(ex, "Failed to launch consent prompt");
            return null;
        }
    }
}
