using System.Collections.ObjectModel;
using System.IO;
using System.Text.Json;
using System.Windows.Threading;
using Alpaca.Markets;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace PaperTradingDesk;

public partial class TradingViewModel : ObservableObject
{
    private readonly AlpacaClient _client;
    private readonly DispatcherTimer _timer;
    private readonly string _statePath;
    private decimal _cashStart = 100_000m;

    [ObservableProperty] private decimal _cash = 100_000m;
    [ObservableProperty] private decimal _portfolioValue;
    [ObservableProperty] private decimal _equity = 100_000m;
    [ObservableProperty] private decimal _pnl;
    [ObservableProperty] private double _pnlPercent;
    [ObservableProperty] private WatchItem? _selected;
    [ObservableProperty] private long _orderQty = 10;
    [ObservableProperty] private string _statusText = "Offline (no API keys)";
    [ObservableProperty] private bool _isLive;

    public ObservableCollection<WatchItem> Watchlist { get; } = new();
    public ObservableCollection<Position> Positions { get; } = new();

    public TradingViewModel(string apiKey, string apiSecret, string[] symbols)
    {
        _statePath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "RLEnv", "trading_state.json");
        Directory.CreateDirectory(Path.GetDirectoryName(_statePath)!);

        _client = new AlpacaClient(apiKey, apiSecret);
        IsLive = _client.IsLive;
        StatusText = IsLive ? "Live (Alpaca paper)" : "Offline (simulated prices)";

        foreach (var s in symbols)
            Watchlist.Add(new WatchItem { Symbol = s });
        if (Watchlist.Count > 0) Selected = Watchlist[0];

        _timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(1500) };
        _timer.Tick += async (_, _) => await RefreshAsync();
        _timer.Start();
        _ = RefreshAsync();
    }

    [RelayCommand]
    private async Task BuyAsync()
    {
        if (Selected is null) return;
        await Trade(Selected, OrderSide.Buy);
    }

    [RelayCommand]
    private async Task SellAsync()
    {
        if (Selected is null) return;
        await Trade(Selected, OrderSide.Sell);
    }

    private async Task Trade(WatchItem item, OrderSide side)
    {
        var price = item.LastPrice;
        if (price <= 0) return;

        var delta = side == OrderSide.Buy ? OrderQty : -OrderQty;
        var pos = Positions.FirstOrDefault(p => p.Symbol == item.Symbol);
        if (pos is null && delta > 0)
        {
            pos = new Position { Symbol = item.Symbol };
            Positions.Add(pos);
        }
        if (pos is null) return;

        var notional = delta * price;
        if (side == OrderSide.Buy && Cash < notional) return;
        if (side == OrderSide.Sell && pos.Qty < OrderQty) return;

        // Update local books optimistically
        var newQty = pos.Qty + delta;
        var totalCost = pos.Qty * pos.AvgPrice + delta * price;
        pos.AvgPrice = newQty > 0 ? totalCost / newQty : 0;
        pos.Qty = newQty;
        Cash -= notional;
        if (pos.Qty == 0) Positions.Remove(pos);

        await _client.PlaceMarketOrderAsync(item.Symbol, OrderQty, side).ConfigureAwait(true);
        await RefreshAsync().ConfigureAwait(true);
    }

    private async Task RefreshAsync()
    {
        decimal positionsValue = 0;
        foreach (var w in Watchlist)
        {
            w.LastPrice = await _client.GetLastPriceAsync(w.Symbol).ConfigureAwait(true);
            var pos = Positions.FirstOrDefault(p => p.Symbol == w.Symbol);
            if (pos is not null)
            {
                pos.MarketValue = pos.Qty * w.LastPrice;
                pos.UnrealizedPnl = pos.MarketValue - pos.Qty * pos.AvgPrice;
                positionsValue += pos.MarketValue;
            }
        }

        PortfolioValue = positionsValue;
        Equity = Cash + positionsValue;
        Pnl = Equity - _cashStart;
        PnlPercent = (double)(Pnl / _cashStart * 100m);

        WriteState();
    }

    private void WriteState()
    {
        try
        {
            var state = new
            {
                ts = DateTimeOffset.UtcNow,
                cash = Cash,
                portfolioValue = PortfolioValue,
                equity = Equity,
                pnl = Pnl,
                pnlPercent = PnlPercent,
                positions = Positions.Select(p => new
                {
                    p.Symbol, p.Qty, p.AvgPrice, p.MarketValue, p.UnrealizedPnl
                }),
                quotes = Watchlist.ToDictionary(w => w.Symbol, w => w.LastPrice),
                isLive = IsLive,
            };
            File.WriteAllText(_statePath,
                JsonSerializer.Serialize(state, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch { }
    }
}

public partial class WatchItem : ObservableObject
{
    [ObservableProperty] private string _symbol = "";
    [ObservableProperty] private decimal _lastPrice;
}

public partial class Position : ObservableObject
{
    [ObservableProperty] private string _symbol = "";
    [ObservableProperty] private long _qty;
    [ObservableProperty] private decimal _avgPrice;
    [ObservableProperty] private decimal _marketValue;
    [ObservableProperty] private decimal _unrealizedPnl;
}
