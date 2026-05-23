using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using TechSupport.Shared.Crypto;

namespace TechSupport.Agent;

/// <summary>
/// Top-level lifetime owner. Generates the pairing code on first run,
/// reports the agent's identity to logs, and keeps the registry alive.
/// In v1 this also dials the relay and registers under the pairing token;
/// for v0 we surface the pairing code and rely on LAN direct connect.
/// </summary>
public sealed class AgentService : BackgroundService
{
    private readonly ILogger<AgentService> _log;
    private readonly AgentOptions _options;
    private readonly SessionRegistry _registry;

    public AgentService(
        ILogger<AgentService> log,
        IOptions<AgentOptions> options,
        SessionRegistry registry)
    {
        _log = log;
        _options = options.Value;
        _registry = registry;
    }

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        var pairingCode = SessionKey.Generate();
        _log.LogInformation(
            "TechSupport.Agent online. Pairing code: {Code} (fingerprint {Fp})",
            pairingCode, SessionKey.Fingerprint(pairingCode));

        if (_options.EnableLanDirect)
            _log.LogInformation(
                "LAN direct listener on {Host}:{Port}",
                _options.ListenHost, _options.ListenPort);

        while (!ct.IsCancellationRequested)
        {
            await Task.Delay(TimeSpan.FromSeconds(30), ct).ConfigureAwait(false);
            _log.LogDebug("Active sessions: {N}", _registry.Active.Count);
        }
    }
}
