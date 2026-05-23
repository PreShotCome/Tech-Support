using System.Collections.ObjectModel;
using System.Text.Json.Serialization;
using CommunityToolkit.Mvvm.ComponentModel;

namespace TechSupport.Console.Models;

public partial class Customer : ObservableObject
{
    [ObservableProperty] private string _id = Guid.NewGuid().ToString("N");
    [ObservableProperty] private string _name = "";
    [ObservableProperty] private string? _organization;
    [ObservableProperty] private string? _phoneNumber;
    [ObservableProperty] private string? _email;
    [ObservableProperty] private string? _notes;
    [ObservableProperty] private string? _color;
    [ObservableProperty] private DateTimeOffset _createdUtc = DateTimeOffset.UtcNow;
    [ObservableProperty] private DateTimeOffset? _lastSessionUtc;
    [ObservableProperty] private int _sessionCount;

    public ObservableCollection<SavedConnection> Connections { get; init; } = new();
    public ObservableCollection<SessionRecord> History { get; init; } = new();

    [JsonIgnore]
    public string Initials
    {
        get
        {
            if (string.IsNullOrWhiteSpace(Name)) return "?";
            var parts = Name.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 1) return parts[0][..1].ToUpperInvariant();
            return $"{parts[0][0]}{parts[^1][0]}".ToUpperInvariant();
        }
    }

    partial void OnNameChanged(string value) => OnPropertyChanged(nameof(Initials));
}
