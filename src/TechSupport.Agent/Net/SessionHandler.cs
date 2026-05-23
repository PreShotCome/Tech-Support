using System.Buffers;
using System.IO.Pipelines;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using Microsoft.Extensions.Logging;
using TechSupport.Agent.Capture;
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
    private readonly ILogger _log;
    private readonly string _remote;
    private Session? _session;

    public SessionHandler(
        TcpClient client,
        IScreenCapture capture,
        IInputInjector injector,
        SessionRegistry registry,
        ILogger log,
        string remote)
    {
        _client = client;
        _capture = capture;
        _injector = injector;
        _registry = registry;
        _log = log;
        _remote = remote;
    }

    public async Task RunAsync(CancellationToken ct)
    {
        var stream = _client.GetStream();
        var reader = PipeReader.Create(stream);

        var (helloType, helloPayload) = await FrameCodec.ReadAsync(reader, ct).ConfigureAwait(false);
        if (helloType != MessageType.Hello)
            throw new InvalidOperationException($"Expected Hello, got {helloType}");

        var hello = JsonMessages.Decode<HelloMessage>(helloPayload);
        var sessionId = Guid.NewGuid().ToString("N");

        var ack = new HelloAckMessage(sessionId, "0.1.0", RequireConsent: false);
        await FrameCodec.WriteAsync(stream, MessageType.HelloAck, JsonMessages.Encode(ack), ct)
            .ConfigureAwait(false);

        _session = new Session(sessionId, hello.AgentId, hello.MachineName, DateTimeOffset.UtcNow, _remote);
        _registry.TryAdd(_session);

        _capture.Initialize(displayIndex: 0);

        var info = new DisplayInfoMessage(
            _capture.Width, _capture.Height, 96, 96, _capture.DisplayIndex, 1);
        await FrameCodec.WriteAsync(stream, MessageType.DisplayInfo, JsonMessages.Encode(info), ct)
            .ConfigureAwait(false);

        var frameTask = PumpFramesAsync(stream, ct);
        var inputTask = PumpInputAsync(reader, ct);
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

                await FrameCodec.WriteAsync(stream, MessageType.FrameKey, headerJson, ct)
                    .ConfigureAwait(false);

                var size = frame.Stride * frame.Height;
                var buffer = ArrayPool<byte>.Shared.Rent(size);
                try
                {
                    Marshal.Copy(frame.Bgra, buffer, 0, size);
                    await stream.WriteAsync(buffer.AsMemory(0, size), ct).ConfigureAwait(false);
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

    private async Task PumpInputAsync(PipeReader reader, CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            var (type, payload) = await FrameCodec.ReadAsync(reader, ct).ConfigureAwait(false);
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
