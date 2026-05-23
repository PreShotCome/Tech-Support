using System.Windows.Controls;

namespace TechSupport.Console.Views.Pages;

public partial class CustomersPage : Page
{
    public CustomersPage()
    {
        InitializeComponent();
        DataContext = App.ViewModel;
    }
}
