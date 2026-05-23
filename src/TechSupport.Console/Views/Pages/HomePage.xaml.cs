using System.Windows.Controls;

namespace TechSupport.Console.Views.Pages;

public partial class HomePage : Page
{
    public HomePage()
    {
        InitializeComponent();
        DataContext = App.Main;
    }
}
