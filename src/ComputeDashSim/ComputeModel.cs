using System.IO;
using System.Text.Json;
using System.Windows.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace ComputeDashSim;

public enum HashAlgo { Ethash, KawPow, Autolykos, RandomX }

public partial class ComputeModel : ObservableObject
{
    private readonly DispatcherTimer _timer;
    private readonly Random _rng = new();
    private readonly string _statePath;

    [ObservableProperty] private bool _isRunning;
    [ObservableProperty] private HashAlgo _algorithm = HashAlgo.Ethash;
    [ObservableProperty] private int _fanPercent = 60;
    [ObservableProperty] private double _hashRateMhs;
    [ObservableProperty] private double _temperatureC = 42;
    [ObservableProperty] private double _powerWatts;
    [ObservableProperty] private long _acceptedShares;
    [ObservableProperty] private long _rejectedShares;
    [ObservableProperty] private string _statusText = "Idle";
    [ObservableProperty] private bool _hasAlert;
    [ObservableProperty] private string _alertText = "";

    public ComputeModel()
    {
        _statePath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "RLEnv", "compute_state.json");
        Directory.CreateDirectory(Path.GetDirectoryName(_statePath)!);

        _timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(500) };
        _timer.Tick += (_, _) => Tick();
        _timer.Start();
        WriteState();
    }

    [RelayCommand]
    private void Toggle()
    {
        IsRunning = !IsRunning;
        StatusText = IsRunning ? "Mining" : "Idle";
        if (!IsRunning)
        {
            HashRateMhs = 0;
            PowerWatts = 0;
            HasAlert = false;
            AlertText = "";
        }
    }

    private void Tick()
    {
        if (IsRunning)
        {
            var target = Algorithm switch
            {
                HashAlgo.Ethash => 60,
                HashAlgo.KawPow => 30,
                HashAlgo.Autolykos => 180,
                HashAlgo.RandomX => 8,
                _ => 50,
            };
            HashRateMhs = target + (_rng.NextDouble() - 0.5) * target * 0.1;

            var fanCooling = 1.0 - (FanPercent / 200.0);
            TemperatureC = Math.Min(95, TemperatureC + fanCooling * 0.7 + (_rng.NextDouble() - 0.5) * 0.3);
            PowerWatts = 120 + (FanPercent / 100.0) * 60 + (_rng.NextDouble() - 0.5) * 10;

            if (_rng.NextDouble() < 0.4)
            {
                if (_rng.NextDouble() < 0.95) AcceptedShares++;
                else RejectedShares++;
            }

            HasAlert = TemperatureC > 80;
            AlertText = HasAlert ? $"GPU at {TemperatureC:F0}°C — raise fan or reduce load" : "";
        }
        else
        {
            TemperatureC = Math.Max(38, TemperatureC - 0.5);
        }

        WriteState();
    }

    private void WriteState()
    {
        var state = new
        {
            ts = DateTimeOffset.UtcNow,
            running = IsRunning,
            algorithm = Algorithm.ToString(),
            fanPercent = FanPercent,
            hashRateMhs = HashRateMhs,
            temperatureC = TemperatureC,
            powerWatts = PowerWatts,
            acceptedShares = AcceptedShares,
            rejectedShares = RejectedShares,
            hasAlert = HasAlert,
            alertText = AlertText,
        };
        try
        {
            File.WriteAllText(_statePath,
                JsonSerializer.Serialize(state, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch { /* don't take down the UI thread over a stat write */ }
    }
}
