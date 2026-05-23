using System.Windows.Controls;

namespace TechSupport.Console.Views.Pages;

public partial class SettingsPage : Page
{
    public SettingsPage()
    {
        InitializeComponent();
        DataContext = App.ViewModel;
    }
}
