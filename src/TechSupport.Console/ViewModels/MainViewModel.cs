using CommunityToolkit.Mvvm.ComponentModel;
using TechSupport.Console.Services;

namespace TechSupport.Console.ViewModels;

public partial class MainViewModel : ObservableObject
{
    [ObservableProperty] private SessionViewModel? _activeSession;
    [ObservableProperty] private string _statusText = "Ready";

    public CustomerStore Store { get; }
    public HomeViewModel Home { get; }
    public CustomersViewModel Customers { get; }
    public HistoryViewModel History { get; }
    public SettingsViewModel Settings { get; }

    public MainViewModel(CustomerStore store)
    {
        Store = store;
        Home = new HomeViewModel(this);
        Customers = new CustomersViewModel(this);
        History = new HistoryViewModel(this);
        Settings = new SettingsViewModel();
    }

    internal void SetStatus(string text) => StatusText = text;

    internal async Task<SessionViewModel?> StartSessionAsync(
        string host, int port, string? customerId)
    {
        StatusText = $"Connecting to {host}:{port}…";
        var session = new SessionViewModel(host, port, customerId)
        {
            TechnicianName = Settings.TechnicianName,
        };
        try
        {
            await session.ConnectAsync().ConfigureAwait(true);
            ActiveSession = session;
            StatusText = $"Connected — {host}:{port}";

            if (customerId is not null)
            {
                var customer = Store.Customers.FirstOrDefault(c => c.Id == customerId);
                if (customer is not null)
                {
                    customer.LastSessionUtc = DateTimeOffset.UtcNow;
                    customer.SessionCount++;
                    customer.History.Insert(0, new Models.SessionRecord
                    {
                        CustomerId = customerId,
                        Host = host,
                        Port = port,
                    });
                    Store.RequestSave();
                }
            }

            return session;
        }
        catch (Exception ex)
        {
            StatusText = $"Connect failed: {ex.Message}";
            return null;
        }
    }

    internal async Task EndSessionAsync()
    {
        if (ActiveSession is null) return;
        var session = ActiveSession;
        ActiveSession = null;

        if (session.CustomerId is { } cid)
        {
            var customer = Store.Customers.FirstOrDefault(c => c.Id == cid);
            var record = customer?.History.FirstOrDefault(r => r.EndedUtc is null);
            if (record is not null)
            {
                record.EndedUtc = DateTimeOffset.UtcNow;
                Store.RequestSave();
            }
        }

        await session.DisposeAsync().ConfigureAwait(true);
        StatusText = "Disconnected.";
    }
}
