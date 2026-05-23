using System.IO;
using CommunityToolkit.Mvvm.ComponentModel;

namespace TechSupport.Console.ViewModels;

public partial class SettingsViewModel : ObservableObject
{
    [ObservableProperty] private string _technicianName = Environment.UserName;
    [ObservableProperty] private string _dataFolder = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "TechSupport");
    [ObservableProperty] private int _defaultPort = 7022;
}
