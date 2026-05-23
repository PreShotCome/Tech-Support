using System.Windows;
using TechSupport.Console.Services;
using TechSupport.Console.ViewModels;

namespace TechSupport.Console;

public partial class App : Application
{
    public static CustomerStore Store { get; } = new();
    public static MainViewModel ViewModel { get; } = new(Store);
}
