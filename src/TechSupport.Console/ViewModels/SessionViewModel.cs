using System.Windows;
using System.Windows.Media.Imaging;
using CommunityToolkit.Mvvm.ComponentModel;
using TechSupport.Console.Services;
using TechSupport.Shared.Protocol;

namespace TechSupport.Console.ViewModels;

public partial class SessionViewModel : ObservableObject, IAsyncDisposable
{
    private readonly string _host;
    private readonly int _port;
    private readonly AgentConnection _connection = new();
    private WriteableBitmap? _bitmap;

    [ObservableProperty] private string _title;
    [ObservableProperty] private WriteableBitmap? _frameBitmap;
    [ObservableProperty] private int _displayWidth;
    [ObservableProperty] private int _displayHeight;
    [ObservableProperty] private double _latencyMs;

    public SessionViewModel(string host, int port)
    {
        _host = host;
        _port = port;
        _title = $"{host}:{port}";
    }

    public async Task ConnectAsync()
    {
        _connection.FrameReceived += OnFrame;
        _connection.Disconnected += OnDisconnected;
        await _connection.ConnectAsync(_host, _port, Environment.UserName, CancellationToken.None)
            .ConfigureAwait(true);

        if (_connection.Display is { } d)
        {
            DisplayWidth = d.Width;
            DisplayHeight = d.Height;
            _bitmap = new WriteableBitmap(
                d.Width, d.Height, 96, 96,
                System.Windows.Media.PixelFormats.Bgra32, null);
            FrameBitmap = _bitmap;
        }
    }

    private void OnFrame(FrameHeader header, byte[] data)
    {
        Application.Current?.Dispatcher.Invoke(() =>
        {
            if (_bitmap is null) return;
            var rect = new System.Windows.Int32Rect(0, 0, header.Width, header.Height);
            _bitmap.WritePixels(rect, data, header.Stride, 0);
            var nowUs = DateTime.UtcNow.Ticks / (TimeSpan.TicksPerMillisecond / 1000);
            LatencyMs = Math.Max(0, (nowUs - header.TimestampUs) / 1000.0);
        });
    }

    private void OnDisconnected(string reason)
    {
        Application.Current?.Dispatcher.Invoke(() =>
            Title = $"{_host}:{_port} — disconnected ({reason})");
    }

    public Task SendMouseMoveAsync(int x, int y) =>
        _connection.SendMouseMoveAsync(x, y);

    public Task SendMouseButtonAsync(int x, int y, MouseButton b, bool pressed) =>
        _connection.SendMouseButtonAsync(x, y, b, pressed);

    public Task SendWheelAsync(int x, int y, int dx, int dy) =>
        _connection.SendWheelAsync(x, y, dx, dy);

    public Task SendKeyAsync(int vk, int sc, bool pressed, bool extended) =>
        _connection.SendKeyAsync(vk, sc, pressed, extended);

    public ValueTask DisposeAsync() => _connection.DisposeAsync();
}
