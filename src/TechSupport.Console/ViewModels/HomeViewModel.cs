using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TechSupport.Console.Models;

namespace TechSupport.Console.ViewModels;

public partial class HomeViewModel : ObservableObject
{
    private readonly MainViewModel _main;

    [ObservableProperty] private string _quickConnectHost = "";
    [ObservableProperty] private int _quickConnectPort = 7022;

    public HomeViewModel(MainViewModel main) => _main = main;

    public IEnumerable<RecentEntry> Recent =>
        _main.Store.Customers
            .Where(c => c.LastSessionUtc is not null)
            .OrderByDescending(c => c.LastSessionUtc)
            .Take(5)
            .SelectMany(c => c.Connections.Take(1).Select(conn =>
                new RecentEntry(c, conn)));

    public SessionViewModel? ActiveSession => _main.ActiveSession;

    [RelayCommand]
    private async Task ConnectAsync()
    {
        if (string.IsNullOrWhiteSpace(QuickConnectHost))
        {
            _main.SetStatus("Enter a host or pick a customer.");
            return;
        }
        await _main.StartSessionAsync(QuickConnectHost, QuickConnectPort, customerId: null)
            .ConfigureAwait(true);
        OnPropertyChanged(nameof(ActiveSession));
    }

    [RelayCommand]
    private async Task ConnectRecentAsync(RecentEntry? entry)
    {
        if (entry is null) return;
        await _main.StartSessionAsync(
            entry.Connection.Host, entry.Connection.Port, entry.Customer.Id)
            .ConfigureAwait(true);
        OnPropertyChanged(nameof(ActiveSession));
    }

    [RelayCommand]
    private async Task DisconnectAsync()
    {
        await _main.EndSessionAsync().ConfigureAwait(true);
        OnPropertyChanged(nameof(ActiveSession));
    }
}

public sealed record RecentEntry(Customer Customer, SavedConnection Connection);
