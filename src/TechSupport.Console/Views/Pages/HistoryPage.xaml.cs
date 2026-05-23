using System.Windows.Controls;

namespace TechSupport.Console.Views.Pages;

public partial class HistoryPage : Page
{
    public HistoryPage()
    {
        InitializeComponent();
        DataContext = App.ViewModel;
    }
}
