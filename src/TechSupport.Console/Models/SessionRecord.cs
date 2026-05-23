using CommunityToolkit.Mvvm.ComponentModel;

namespace TechSupport.Console.Models;

public partial class SessionRecord : ObservableObject
{
    [ObservableProperty] private string _id = Guid.NewGuid().ToString("N");
    [ObservableProperty] private string? _customerId;
    [ObservableProperty] private string _host = "";
    [ObservableProperty] private int _port;
    [ObservableProperty] private DateTimeOffset _startedUtc = DateTimeOffset.UtcNow;
    [ObservableProperty] private DateTimeOffset? _endedUtc;
    [ObservableProperty] private string? _summary;
    [ObservableProperty] private string? _outcome;

    public TimeSpan Duration =>
        (EndedUtc ?? DateTimeOffset.UtcNow) - StartedUtc;
}
