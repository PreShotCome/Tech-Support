using Wpf.Ui.Controls;

namespace TechSupport.Console.Views;

public partial class MainWindow : FluentWindow
{
    public MainWindow()
    {
        InitializeComponent();
        DataContext = App.ViewModel;
    }
}
