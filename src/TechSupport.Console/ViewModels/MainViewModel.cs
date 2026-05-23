using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TechSupport.Console.Models;

namespace TechSupport.Console.ViewModels;

public partial class MainViewModel : ObservableObject
{
    [ObservableProperty] private string _quickConnectHost = "";
    [ObservableProperty] private int _quickConnectPort = 7022;
    [ObservableProperty] private SavedConnection? _selectedConnection;
    [ObservableProperty] private SessionViewModel? _activeSession;
    [ObservableProperty] private string _statusText = "Ready";

    public ObservableCollection<SavedConnection> SavedConnections { get; } = new();
    public ObservableCollection<Customer> Customers { get; } = new();

    public MainViewModel()
    {
        SavedConnections.Add(new SavedConnection
        {
            Id = "demo",
            Label = "Demo workstation",
            Host = "192.168.1.50",
            Port = 7022,
        });
    }

    [RelayCommand]
    private async Task ConnectAsync()
    {
        var host = SelectedConnection?.Host ?? QuickConnectHost;
        var port = SelectedConnection?.Port ?? QuickConnectPort;
        if (string.IsNullOrWhiteSpace(host))
        {
            StatusText = "Enter a host or pick a saved connection.";
            return;
        }

        StatusText = $"Connecting to {host}:{port}…";
        var session = new SessionViewModel(host, port);
        try
        {
            await session.ConnectAsync().ConfigureAwait(true);
            ActiveSession = session;
            StatusText = $"Connected — {host}:{port}";
        }
        catch (Exception ex)
        {
            StatusText = $"Connect failed: {ex.Message}";
        }
    }

    [RelayCommand]
    private async Task DisconnectAsync()
    {
        if (ActiveSession is null) return;
        await ActiveSession.DisposeAsync().ConfigureAwait(true);
        ActiveSession = null;
        StatusText = "Disconnected.";
    }
}
