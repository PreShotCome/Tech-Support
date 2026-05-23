using System.IO;
using System.Windows;
using System.Windows.Threading;
using TechSupport.Console.Services;
using TechSupport.Console.ViewModels;

namespace TechSupport.Console;

public partial class App : Application
{
    public static CustomerStore Store { get; } = new();
    public static MainViewModel ViewModel { get; } = new(Store);

    public static readonly string CrashLogPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "TechSupport", "console-crash.log");

    public App()
    {
        AppDomain.CurrentDomain.UnhandledException += (_, e) =>
            WriteCrash("AppDomain.UnhandledException", e.ExceptionObject as Exception);
        DispatcherUnhandledException += (_, e) =>
        {
            WriteCrash("Dispatcher.UnhandledException", e.Exception);
            e.Handled = false;
        };
        TaskScheduler.UnobservedTaskException += (_, e) =>
        {
            WriteCrash("TaskScheduler.UnobservedTaskException", e.Exception);
            e.SetObserved();
        };
    }

    private static void WriteCrash(string source, Exception? ex)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(CrashLogPath)!);
            var line = $"[{DateTimeOffset.Now:O}] {source}\n{ex}\n\n";
            File.AppendAllText(CrashLogPath, line);
        }
        catch { /* don't crash inside the crash handler */ }
    }
}

