using System.IO;
using System.Text.Json;
using Wpf.Ui.Controls;

namespace PaperTradingDesk;

public partial class MainWindow : FluentWindow
{
    public MainWindow()
    {
        InitializeComponent();
        var (key, secret, symbols) = LoadConfig();
        DataContext = new TradingViewModel(key, secret, symbols);
    }

    private static (string key, string secret, string[] symbols) LoadConfig()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "appsettings.json");
        if (!File.Exists(path))
            return ("", "", new[] { "AAPL", "MSFT", "NVDA", "TSLA", "SPY" });

        using var stream = File.OpenRead(path);
        var doc = JsonDocument.Parse(stream);
        var alpaca = doc.RootElement.GetProperty("Alpaca");
        var key = alpaca.TryGetProperty("KeyId", out var k) ? k.GetString() ?? "" : "";
        var secret = alpaca.TryGetProperty("SecretKey", out var s) ? s.GetString() ?? "" : "";
        var symbols = alpaca.TryGetProperty("Symbols", out var arr)
            ? arr.EnumerateArray().Select(e => e.GetString() ?? "").Where(x => x != "").ToArray()
            : new[] { "AAPL", "MSFT", "NVDA", "TSLA", "SPY" };
        return (key, secret, symbols);
    }
}
