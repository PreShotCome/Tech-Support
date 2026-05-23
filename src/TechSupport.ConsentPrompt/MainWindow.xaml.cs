using System.Windows;
using System.Windows.Threading;
using TechSupport.Shared.Protocol;
using Wpf.Ui.Controls;

namespace TechSupport.ConsentPrompt;

public partial class MainWindow : FluentWindow
{
    private readonly DispatcherTimer _timer;
    private int _remainingSeconds;

    public string TechnicianName { get; }
    public string Reason { get; }

    public MainWindow(ConsentPromptMessage prompt)
    {
        TechnicianName = prompt.TechnicianName;
        Reason = string.IsNullOrWhiteSpace(prompt.Reason) ? "(no reason given)" : prompt.Reason;
        _remainingSeconds = prompt.TimeoutSeconds;

        InitializeComponent();
        DataContext = this;

        _timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
        _timer.Tick += OnTick;
        _timer.Start();
        UpdateCountdown();
    }

    private void OnTick(object? sender, EventArgs e)
    {
        _remainingSeconds--;
        if (_remainingSeconds <= 0)
        {
            _timer.Stop();
            DialogResult = false;
            Close();
            return;
        }
        UpdateCountdown();
    }

    private void UpdateCountdown() =>
        Countdown.Text = $"Auto-deny in {_remainingSeconds}s.";

    private void OnAllow(object sender, RoutedEventArgs e)
    {
        _timer.Stop();
        DialogResult = true;
        Close();
    }

    private void OnDeny(object sender, RoutedEventArgs e)
    {
        _timer.Stop();
        DialogResult = false;
        Close();
    }
}
