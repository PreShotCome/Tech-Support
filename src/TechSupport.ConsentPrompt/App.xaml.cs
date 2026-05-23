using System.IO;
using System.IO.Pipes;
using System.Windows;
using System.Windows.Threading;
using TechSupport.Shared.Protocol;

namespace TechSupport.ConsentPrompt;

public partial class App : Application
{
    public static readonly string CrashLogPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "TechSupport", "consent-crash.log");

    public App()
    {
        AppDomain.CurrentDomain.UnhandledException += (_, e) =>
            WriteCrash("AppDomain.UnhandledException", e.ExceptionObject as Exception);
        DispatcherUnhandledException += (_, e) =>
        {
            WriteCrash("Dispatcher.UnhandledException", e.Exception);
            e.Handled = false;
        };
    }

    private static void WriteCrash(string source, Exception? ex)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(CrashLogPath)!);
            File.AppendAllText(CrashLogPath,
                $"[{DateTimeOffset.Now:O}] {source}\n{ex}\n\n");
        }
        catch { /* don't crash in the crash handler */ }
    }

    private static void Log(string line)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(CrashLogPath)!);
            File.AppendAllText(CrashLogPath,
                $"[{DateTimeOffset.Now:O}] INFO {line}\n");
        }
        catch { /* ignore */ }
    }

    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        Log($"OnStartup args=[{string.Join(' ', e.Args)}]");

        if (e.Args.Length < 1)
        {
            MessageBox.Show("Missing pipe name argument.", "TechSupport consent",
                MessageBoxButton.OK, MessageBoxImage.Error);
            Shutdown(2);
            return;
        }

        var pipeName = e.Args[0];

        try
        {
            await using var pipe = new NamedPipeClientStream(
                ".", pipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
            await pipe.ConnectAsync(5000).ConfigureAwait(true);
            Log($"Connected to pipe {pipeName}");

            var reader = System.IO.Pipelines.PipeReader.Create(pipe);
            var (type, payload) = await FrameCodec.ReadAsync(reader).ConfigureAwait(true);
            if (type != MessageType.ConsentPrompt)
            {
                Log($"Unexpected first message: {type}");
                Shutdown(3);
                return;
            }
            var prompt = JsonMessages.Decode<ConsentPromptMessage>(payload);

            var window = new MainWindow(prompt);
            MainWindow = window;
            var allowed = window.ShowDialog() == true;
            Log($"User decision: allowed={allowed}");

            await FrameCodec.WriteAsync(
                pipe,
                allowed ? MessageType.ConsentGranted : MessageType.ConsentDenied,
                ReadOnlyMemory<byte>.Empty).ConfigureAwait(true);

            Shutdown(allowed ? 0 : 1);
        }
        catch (Exception ex)
        {
            WriteCrash("OnStartup.catch", ex);
            try
            {
                MessageBox.Show($"Consent prompt failed: {ex.Message}", "TechSupport consent",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
            catch { /* ignore */ }
            Shutdown(2);
        }
    }
}
