using System.Buffers;
using System.IO;
using System.Net.Sockets;
using TechSupport.Shared.Protocol;

namespace TechSupport.Console.Services;

internal static class ConnLog
{
    private static readonly string Path = System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "TechSupport", "console-conn.log");

    public static void Write(string line)
    {
        try
        {
            Directory.CreateDirectory(System.IO.Path.GetDirectoryName(Path)!);
            File.AppendAllText(Path,
                $"[{DateTimeOffset.Now:O}] T{Environment.CurrentManagedThreadId:D3} {line}\n");
        }
        catch { /* ignore */ }
    }
}

/// <summary>
/// Technician-side counterpart to SessionHandler. Establishes the TCP
/// session with an agent, exchanges Hello, and exposes:
///   - an async stream of decoded frames (consumed by RemoteDesktopView)
///   - methods to push input events
/// </summary>
public sealed class AgentConnection : IAsyncDisposable
{
    private readonly TcpClient _client = new();
    private NetworkStream? _stream;
    private CancellationTokenSource? _cts;

    public DisplayInfoMessage? Display { get; private set; }
    public string? SessionId { get; private set; }

    public event Action<FrameHeader, byte[]>? FrameReceived;
    public event Action<string>? Disconnected;

    public async Task ConnectAsync(string host, int port, string technicianName, CancellationToken ct)
    {
        ConnLog.Write($"ConnectAsync entered host={host} port={port} user={technicianName}");
        await _client.ConnectAsync(host, port, ct).ConfigureAwait(false);
        _client.NoDelay = true;
        _stream = _client.GetStream();
        ConnLog.Write("TCP connected, NoDelay set, stream created");

        var hello = new HelloMessage(
            AgentId: "console",
            MachineName: Environment.MachineName,
            OsVersion: Environment.OSVersion.VersionString,
            AgentVersion: "0.1.0",
            Capabilities: new[] { "input.mouse", "input.keyboard" },
            TechnicianName: technicianName);

        var helloBytes = JsonMessages.Encode(hello);
        ConnLog.Write($"About to write Hello, payload={helloBytes.Length} bytes");
        await FrameCodec.WriteAsync(_stream, MessageType.Hello, helloBytes, ct).ConfigureAwait(false);
        ConnLog.Write("Hello written; awaiting HelloAck");

        var (ackType, ackPayload) = await FrameCodec.ReadFromStreamAsync(_stream, ct).ConfigureAwait(false);
        ConnLog.Write($"Received {ackType} ({ackPayload.Length} bytes)");
        if (ackType != MessageType.HelloAck)
            throw new InvalidOperationException($"Expected HelloAck, got {ackType}");
        var ack = JsonMessages.Decode<HelloAckMessage>(ackPayload);
        SessionId = ack.SessionId;

        if (ack.RequireConsent)
        {
            ConnLog.Write("Awaiting consent response from agent");
            var (consentType, _) = await FrameCodec.ReadFromStreamAsync(_stream, ct).ConfigureAwait(false);
            ConnLog.Write($"Consent response: {consentType}");
            if (consentType == MessageType.ConsentDenied)
                throw new UnauthorizedAccessException(
                    "The end user denied or ignored the consent prompt.");
            if (consentType != MessageType.ConsentGranted)
                throw new InvalidOperationException(
                    $"Expected consent response, got {consentType}");
        }

        var (infoType, infoPayload) = await FrameCodec.ReadFromStreamAsync(_stream, ct).ConfigureAwait(false);
        if (infoType != MessageType.DisplayInfo)
            throw new InvalidOperationException($"Expected DisplayInfo, got {infoType}");
        Display = JsonMessages.Decode<DisplayInfoMessage>(infoPayload);

        _cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        _ = Task.Run(() => ReadLoopAsync(_cts.Token));
    }

    private async Task ReadLoopAsync(CancellationToken ct)
    {
        try
        {
            while (!ct.IsCancellationRequested && _stream is not null)
            {
                var (type, payload) = await FrameCodec.ReadFromStreamAsync(_stream, ct).ConfigureAwait(false);
                if (type is MessageType.FrameKey or MessageType.FrameDelta)
                {
                    var header = JsonMessages.Decode<FrameHeader>(payload);
                    var size = header.Stride * header.Height;
                    var buffer = ArrayPool<byte>.Shared.Rent(size);
                    try
                    {
                        await ReadExactAsync(_stream, buffer.AsMemory(0, size), ct)
                            .ConfigureAwait(false);
                        FrameReceived?.Invoke(header, buffer);
                    }
                    finally
                    {
                        ArrayPool<byte>.Shared.Return(buffer);
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Disconnected?.Invoke(ex.Message);
        }
    }

    private static async Task ReadExactAsync(NetworkStream s, Memory<byte> buffer, CancellationToken ct)
    {
        var remaining = buffer;
        while (!remaining.IsEmpty)
        {
            var n = await s.ReadAsync(remaining, ct).ConfigureAwait(false);
            if (n == 0) throw new EndOfStreamException();
            remaining = remaining.Slice(n);
        }
    }

    public Task SendMouseMoveAsync(int x, int y) =>
        Send(MessageType.MouseMove, new MouseMoveMessage(x, y));

    public Task SendMouseButtonAsync(int x, int y, MouseButton b, bool pressed) =>
        Send(MessageType.MouseButton, new MouseButtonMessage(x, y, b, pressed));

    public Task SendWheelAsync(int x, int y, int dx, int dy) =>
        Send(MessageType.MouseWheel, new MouseWheelMessage(x, y, dx, dy));

    public Task SendKeyAsync(int vk, int sc, bool pressed, bool extended) =>
        Send(MessageType.KeyEvent, new KeyEventMessage(vk, sc, pressed, extended));

    private async Task Send<T>(MessageType type, T msg)
    {
        if (_stream is null) return;
        await FrameCodec.WriteAsync(_stream, type, JsonMessages.Encode(msg)).ConfigureAwait(false);
    }

    public async ValueTask DisposeAsync()
    {
        _cts?.Cancel();
        if (_stream is not null)
        {
            try
            {
                await FrameCodec.WriteAsync(_stream, MessageType.Bye, ReadOnlyMemory<byte>.Empty)
                    .ConfigureAwait(false);
            }
            catch { /* best effort */ }
        }
        _client.Dispose();
    }
}
