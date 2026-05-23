using Alpaca.Markets;

namespace PaperTradingDesk;

/// <summary>
/// Thin wrapper around Alpaca's paper-trading SDK. Live calls require
/// API keys in appsettings.json. If keys are missing the client falls
/// back to an offline random-walk simulator so the UI is still useful
/// for development.
/// </summary>
public sealed class AlpacaClient : IAsyncDisposable
{
    private readonly IAlpacaTradingClient? _trading;
    private readonly IAlpacaDataClient? _data;
    private readonly Random _rng = new();

    public bool IsLive { get; }

    public AlpacaClient(string keyId, string secretKey)
    {
        if (string.IsNullOrWhiteSpace(keyId) || string.IsNullOrWhiteSpace(secretKey))
        {
            IsLive = false;
            return;
        }

        var creds = new SecretKey(keyId, secretKey);
        _trading = Environments.Paper.GetAlpacaTradingClient(creds);
        _data = Environments.Paper.GetAlpacaDataClient(creds);
        IsLive = true;
    }

    public async Task<decimal> GetEquityAsync()
    {
        if (!IsLive || _trading is null) return 100_000m;
        var account = await _trading.GetAccountAsync().ConfigureAwait(false);
        return account.Equity ?? 0m;
    }

    public async Task<decimal> GetLastPriceAsync(string symbol)
    {
        if (!IsLive || _data is null) return SimulatedPrice(symbol);
        try
        {
            var quote = await _data.GetLatestTradeAsync(new LatestMarketDataRequest(symbol))
                .ConfigureAwait(false);
            return quote.Price;
        }
        catch
        {
            return SimulatedPrice(symbol);
        }
    }

    public async Task PlaceMarketOrderAsync(string symbol, long qty, OrderSide side)
    {
        if (!IsLive || _trading is null) return;
        await _trading.PostOrderAsync(side switch
        {
            OrderSide.Buy => MarketOrder.Buy(symbol, qty),
            _ => MarketOrder.Sell(symbol, qty),
        }).ConfigureAwait(false);
    }

    private decimal SimulatedPrice(string symbol)
    {
        var seed = symbol.GetHashCode();
        var basePrice = 50m + Math.Abs(seed % 400);
        var jitter = (decimal)((_rng.NextDouble() - 0.5) * 0.5);
        return Math.Max(1m, basePrice + jitter);
    }

    public ValueTask DisposeAsync()
    {
        _trading?.Dispose();
        _data?.Dispose();
        return ValueTask.CompletedTask;
    }
}
