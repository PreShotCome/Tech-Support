using System.Buffers;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using Microsoft.Extensions.Logging;
using TechSupport.Agent.Capture;
using TechSupport.Agent.Consent;
using TechSupport.Agent.Input;
using TechSupport.Shared.Protocol;

namespace TechSupport.Agent.Net;

/// <summary>
/// One technician connection. Negotiates Hello, then runs two pumps:
///   - frame producer: grab a frame, push it to the technician
///   - input consumer: read input messages, inject via SendInput
/// </summary>
public sealed class SessionHandler : IDisposable
{
    private readonly TcpClient _client;
    private readonly IScreenCapture _capture;
    private readonly IInputInjector _injector;
    private readonly SessionRegistry _registry;
    private readonly ConsentBroker _consent;
    private readonly AgentOptions _options;
    private readonly ILogger _log;
    private readonly string _remote;
    private readonly SemaphoreSlim _writeLock = new(1, 1);
    private Session? _session;

    public SessionHandler(
        TcpClient client,
        IScreenCapture capture,
        IInputInjector injector,
        SessionRegistry registry,
        ConsentBroker consent,
        AgentOptions options,
        ILogger log,
        string remote)
    {
        _client = client;
        _capture = capture;
        _injector = injector;
        _registry = registry;
        _consent = consent;
        _options = options;
        _log = log;
        _remote = remote;
    }

    public async Task RunAsync(CancellationToken ct)
    {
        _log.LogInformation("Session {Remote}: handler started", _remote);
        _client.NoDelay = true;
        var stream = _client.GetStream();

        _log.LogInformation("Session {Remote}: waiting for Hello", _remote);
        var (helloType, helloPayload) = await FrameCodec.ReadFromStreamAsync(stream, ct).ConfigureAwait(false);
        _log.LogInformation("Session {Remote}: received {Type} ({Bytes} bytes)",
            _remote, helloType, helloPayload.Length);
        if (helloType != MessageType.Hello)
            throw new InvalidOperationException($"Expected Hello, got {helloType}");

        var hello = JsonMessages.Decode<HelloMessage>(helloPayload);
        var sessionId = Guid.NewGuid().ToString("N");

        var ack = new HelloAckMessage(sessionId, "0.1.0", _options.RequireConsent);
        await FrameCodec.WriteAsync(stream, MessageType.HelloAck, JsonMessages.Encode(ack), ct)
            .ConfigureAwait(false);
        _log.LogInformation("Session {Remote}: HelloAck sent (RequireConsent={Req})",
            _remote, _options.RequireConsent);

        if (_options.RequireConsent)
        {
            var displayName = !string.IsNullOrWhiteSpace(hello.TechnicianName)
                ? hello.TechnicianName
                : $"{hello.MachineName} (unverified)";
            _log.LogInformation("Awaiting consent from local user for technician {Name}",
                displayName);
            var allowed = await _consent.RequestAsync(
                technicianName: displayName,
                reason: hello.Reason ?? "Remote support session",
                timeout: TimeSpan.FromSeconds(_options.ConsentTimeoutSeconds),
                ct: ct).ConfigureAwait(false);
            _log.LogInformation("Consent decision: allowed={Allowed}", allowed);

            if (!allowed)
            {
                _log.LogWarning("Local user denied or ignored consent prompt");
                await FrameCodec.WriteAsync(stream, MessageType.ConsentDenied,
                    ReadOnlyMemory<byte>.Empty, ct).ConfigureAwait(false);
                return;
            }

            await FrameCodec.WriteAsync(stream, MessageType.ConsentGranted,
                ReadOnlyMemory<byte>.Empty, ct).ConfigureAwait(false);
        }

        _session = new Session(sessionId, hello.AgentId, hello.MachineName, DateTimeOffset.UtcNow, _remote);
        _registry.TryAdd(_session);

        _capture.Initialize(displayIndex: 0);

        var info = new DisplayInfoMessage(
            _capture.Width, _capture.Height, 96, 96, _capture.DisplayIndex, 1);
        await FrameCodec.WriteAsync(stream, MessageType.DisplayInfo, JsonMessages.Encode(info), ct)
            .ConfigureAwait(false);

        var frameTask = PumpFramesAsync(stream, ct);
        var inputTask = PumpInputAsync(stream, ct);
        await Task.WhenAny(frameTask, inputTask).ConfigureAwait(false);
    }

    private async Task PumpFramesAsync(NetworkStream stream, CancellationToken ct)
    {
        var targetFps = 30;
        var minFrameInterval = TimeSpan.FromSeconds(1.0 / targetFps);

        while (!ct.IsCancellationRequested)
        {
            var start = DateTime.UtcNow;
            if (!_capture.TryAcquireFrame(50, out var frame))
                continue;

            try
            {
                var header = new FrameHeader(
                    frame.Width, frame.Height, frame.Stride,
                    frame.TimestampUs, frame.IsKeyFrame, "bgra-raw");
                var headerJson = JsonMessages.Encode(header);

                var size = frame.Stride * frame.Height;
                var buffer = ArrayPool<byte>.Shared.Rent(size);
                try
                {
                    Marshal.Copy(frame.Bgra, buffer, 0, size);
                    await _writeLock.WaitAsync(ct).ConfigureAwait(false);
                    try
                    {
                        await FrameCodec.WriteAsync(stream, MessageType.FrameKey, headerJson, ct)
                            .ConfigureAwait(false);
                        await stream.WriteAsync(buffer.AsMemory(0, size), ct).ConfigureAwait(false);
                    }
                    finally
                    {
                        _writeLock.Release();
                    }
                }
                finally
                {
                    ArrayPool<byte>.Shared.Return(buffer);
                }
            }
            finally
            {
                _capture.ReleaseFrame();
            }

            var elapsed = DateTime.UtcNow - start;
            if (elapsed < minFrameInterval)
                await Task.Delay(minFrameInterval - elapsed, ct).ConfigureAwait(false);
        }
    }

    private async Task PumpInputAsync(NetworkStream stream, CancellationToken ct)
    {
        var inputCount = 0;
        while (!ct.IsCancellationRequested)
        {
            var (type, payload) = await FrameCodec.ReadFromStreamAsync(stream, ct).ConfigureAwait(false);
            if (inputCount++ == 0)
                _log.LogInformation("First input message received: {Type}", type);
            switch (type)
            {
                case MessageType.MouseMove:
                    var mm = JsonMessages.Decode<MouseMoveMessage>(payload);
                    _injector.MoveMouse(mm.X, mm.Y);
                    break;
                case MessageType.MouseButton:
                    var mb = JsonMessages.Decode<MouseButtonMessage>(payload);
                    _injector.Button(mb.X, mb.Y, mb.Button, mb.Pressed);
                    break;
                case MessageType.MouseWheel:
                    var mw = JsonMessages.Decode<MouseWheelMessage>(payload);
                    _injector.Wheel(mw.X, mw.Y, mw.DeltaX, mw.DeltaY);
                    break;
                case MessageType.KeyEvent:
                    var k = JsonMessages.Decode<KeyEventMessage>(payload);
                    _injector.Key(k.VirtualKey, k.ScanCode, k.Pressed, k.Extended);
                    break;
                case MessageType.Bye:
                    _log.LogInformation("Technician requested disconnect");
                    return;
            }
        }
    }

    public void Dispose()
    {
        if (_session is not null)
            _registry.TryRemove(_session.Id, out _);
    }
}
