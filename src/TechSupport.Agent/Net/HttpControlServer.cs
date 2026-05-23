using System.Net;
using System.Runtime.Versioning;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using TechSupport.Agent.Capture;
using TechSupport.Agent.Input;
using TechSupport.Shared.Protocol;

namespace TechSupport.Agent.Net;

/// <summary>
/// Minimal HTTP control surface used by the Python RL environment.
/// Endpoints:
///   GET  /info               JSON: width, height, displayIndex
///   GET  /frame              raw BGRA bytes (width*height*4)
///   POST /mouse/move?x=&y=
///   POST /mouse/button?x=&y=&button=&pressed=
///   POST /mouse/wheel?x=&y=&dx=&dy=
///   POST /key?vk=&sc=&pressed=&extended=
///
/// Loopback-only by default; no auth. Bind to 127.0.0.1 when training.
/// </summary>
[SupportedOSPlatform("windows6.2")]
public sealed class HttpControlServer : BackgroundService
{
    private readonly ILogger<HttpControlServer> _log;
    private readonly AgentOptions _options;
    private readonly IScreenCapture _capture;
    private readonly IInputInjector _injector;
    private bool _captureReady;

    public HttpControlServer(
        ILogger<HttpControlServer> log,
        IOptions<AgentOptions> options,
        IScreenCapture capture,
        IInputInjector injector)
    {
        _log = log;
        _options = options.Value;
        _capture = capture;
        _injector = injector;
    }

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        if (!_options.EnableHttpControl)
        {
            _log.LogInformation("HTTP control disabled.");
            return;
        }

        var listener = new HttpListener();
        listener.Prefixes.Add($"http://127.0.0.1:{_options.HttpControlPort}/");
        listener.Start();
        _log.LogInformation("HTTP control listening on http://127.0.0.1:{Port}/",
            _options.HttpControlPort);

        try
        {
            while (!ct.IsCancellationRequested)
            {
                HttpListenerContext ctx;
                try { ctx = await listener.GetContextAsync().ConfigureAwait(false); }
                catch (HttpListenerException) { break; }
                catch (ObjectDisposedException) { break; }

                _ = Task.Run(() => HandleAsync(ctx, ct), ct);
            }
        }
        finally
        {
            listener.Close();
        }
    }

    private async Task HandleAsync(HttpListenerContext ctx, CancellationToken ct)
    {
        try
        {
            var path = ctx.Request.Url?.AbsolutePath ?? "/";
            switch (path)
            {
                case "/info":
                    await WriteInfoAsync(ctx).ConfigureAwait(false);
                    break;
                case "/frame":
                    await WriteFrameAsync(ctx).ConfigureAwait(false);
                    break;
                case "/mouse/move":
                    DoMouseMove(ctx);
                    Ok(ctx);
                    break;
                case "/mouse/button":
                    DoMouseButton(ctx);
                    Ok(ctx);
                    break;
                case "/mouse/wheel":
                    DoMouseWheel(ctx);
                    Ok(ctx);
                    break;
                case "/key":
                    DoKey(ctx);
                    Ok(ctx);
                    break;
                default:
                    ctx.Response.StatusCode = 404;
                    break;
            }
        }
        catch (Exception ex)
        {
            _log.LogWarning(ex, "HTTP control handler error");
            ctx.Response.StatusCode = 500;
            await WriteTextAsync(ctx, ex.Message).ConfigureAwait(false);
        }
        finally
        {
            ctx.Response.Close();
        }
    }

    private void EnsureCapture()
    {
        if (_captureReady) return;
        _capture.Initialize(displayIndex: 0);
        _captureReady = true;
    }

    private async Task WriteInfoAsync(HttpListenerContext ctx)
    {
        EnsureCapture();
        var info = new
        {
            width = _capture.Width,
            height = _capture.Height,
            displayIndex = _capture.DisplayIndex,
            stride = _capture.Width * 4,
            format = "BGRA",
        };
        ctx.Response.ContentType = "application/json";
        var bytes = JsonSerializer.SerializeToUtf8Bytes(info);
        ctx.Response.ContentLength64 = bytes.Length;
        await ctx.Response.OutputStream.WriteAsync(bytes).ConfigureAwait(false);
    }

    private async Task WriteFrameAsync(HttpListenerContext ctx)
    {
        EnsureCapture();
        if (!_capture.TryAcquireFrame(200, out var frame))
        {
            ctx.Response.StatusCode = 204;
            return;
        }
        try
        {
            var size = frame.Stride * frame.Height;
            var buf = new byte[size];
            System.Runtime.InteropServices.Marshal.Copy(frame.Bgra, buf, 0, size);

            ctx.Response.ContentType = "application/octet-stream";
            ctx.Response.Headers["X-Width"] = frame.Width.ToString();
            ctx.Response.Headers["X-Height"] = frame.Height.ToString();
            ctx.Response.Headers["X-Stride"] = frame.Stride.ToString();
            ctx.Response.ContentLength64 = size;
            await ctx.Response.OutputStream.WriteAsync(buf).ConfigureAwait(false);
        }
        finally
        {
            _capture.ReleaseFrame();
        }
    }

    private void DoMouseMove(HttpListenerContext ctx)
    {
        var x = QInt(ctx, "x");
        var y = QInt(ctx, "y");
        _injector.MoveMouse(x, y);
    }

    private void DoMouseButton(HttpListenerContext ctx)
    {
        var x = QInt(ctx, "x");
        var y = QInt(ctx, "y");
        var button = (MouseButton)QInt(ctx, "button");
        var pressed = QInt(ctx, "pressed") != 0;
        _injector.Button(x, y, button, pressed);
    }

    private void DoMouseWheel(HttpListenerContext ctx)
    {
        var x = QInt(ctx, "x");
        var y = QInt(ctx, "y");
        var dx = QInt(ctx, "dx");
        var dy = QInt(ctx, "dy");
        _injector.Wheel(x, y, dx, dy);
    }

    private void DoKey(HttpListenerContext ctx)
    {
        var vk = QInt(ctx, "vk");
        var sc = QInt(ctx, "sc", 0);
        var pressed = QInt(ctx, "pressed") != 0;
        var extended = QInt(ctx, "extended", 0) != 0;
        _injector.Key(vk, sc, pressed, extended);
    }

    private static int QInt(HttpListenerContext ctx, string name, int? fallback = null)
    {
        var v = ctx.Request.QueryString[name];
        if (v is null && fallback is not null) return fallback.Value;
        if (v is null) throw new ArgumentException($"Missing query parameter {name}");
        return int.Parse(v);
    }

    private static void Ok(HttpListenerContext ctx) => ctx.Response.StatusCode = 204;

    private static async Task WriteTextAsync(HttpListenerContext ctx, string text)
    {
        ctx.Response.ContentType = "text/plain; charset=utf-8";
        var bytes = Encoding.UTF8.GetBytes(text);
        ctx.Response.ContentLength64 = bytes.Length;
        await ctx.Response.OutputStream.WriteAsync(bytes).ConfigureAwait(false);
    }
}
