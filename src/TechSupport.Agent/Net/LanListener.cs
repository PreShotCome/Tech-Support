using System.Net;
using System.Net.Sockets;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using TechSupport.Agent.Capture;
using TechSupport.Agent.Input;

namespace TechSupport.Agent.Net;

/// <summary>
/// Accepts direct TCP connections from technician consoles on the local
/// network. Used for v0 testing and as a fallback when the relay is
/// unreachable. Each accepted connection is handled by a SessionHandler.
/// </summary>
public sealed class LanListener : BackgroundService
{
    private readonly ILogger<LanListener> _log;
    private readonly AgentOptions _options;
    private readonly IScreenCapture _capture;
    private readonly IInputInjector _injector;
    private readonly SessionRegistry _registry;

    public LanListener(
        ILogger<LanListener> log,
        IOptions<AgentOptions> options,
        IScreenCapture capture,
        IInputInjector injector,
        SessionRegistry registry)
    {
        _log = log;
        _options = options.Value;
        _capture = capture;
        _injector = injector;
        _registry = registry;
    }

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        if (!_options.EnableLanDirect)
        {
            _log.LogInformation("LAN direct disabled by configuration.");
            return;
        }

        var listener = new TcpListener(IPAddress.Parse(_options.ListenHost), _options.ListenPort);
        listener.Start();

        try
        {
            while (!ct.IsCancellationRequested)
            {
                TcpClient client;
                try { client = await listener.AcceptTcpClientAsync(ct).ConfigureAwait(false); }
                catch (OperationCanceledException) { break; }

                _ = Task.Run(() => HandleAsync(client, ct), ct);
            }
        }
        finally
        {
            listener.Stop();
        }
    }

    private async Task HandleAsync(TcpClient client, CancellationToken ct)
    {
        var remote = client.Client.RemoteEndPoint?.ToString() ?? "unknown";
        _log.LogInformation("Inbound LAN connection from {Remote}", remote);

        try
        {
            using var handler = new SessionHandler(
                client, _capture, _injector, _registry, _log, remote);
            await handler.RunAsync(ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _log.LogWarning(ex, "Session from {Remote} ended with error", remote);
        }
        finally
        {
            client.Dispose();
            _log.LogInformation("Connection from {Remote} closed", remote);
        }
    }
}
