using CommunityToolkit.Mvvm.ComponentModel;

namespace TechSupport.Console.Models;

public partial class SavedConnection : ObservableObject
{
    [ObservableProperty] private string _id = Guid.NewGuid().ToString("N");
    [ObservableProperty] private string _label = "";
    [ObservableProperty] private string _host = "";
    [ObservableProperty] private int _port = 7022;
    [ObservableProperty] private string? _customerId;
    [ObservableProperty] private DateTimeOffset? _lastConnectedUtc;
    [ObservableProperty] private string? _machineId;
}
