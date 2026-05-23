using System.IO.Pipes;
using System.Windows;
using TechSupport.Shared.Protocol;

namespace TechSupport.ConsentPrompt;

public partial class App : Application
{
    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

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

            var reader = System.IO.Pipelines.PipeReader.Create(pipe);
            var (type, payload) = await FrameCodec.ReadAsync(reader).ConfigureAwait(true);
            if (type != MessageType.ConsentPrompt)
            {
                Shutdown(3);
                return;
            }
            var prompt = JsonMessages.Decode<ConsentPromptMessage>(payload);

            var window = new MainWindow(prompt);
            MainWindow = window;
            var allowed = window.ShowDialog() == true;

            await FrameCodec.WriteAsync(
                pipe,
                allowed ? MessageType.ConsentGranted : MessageType.ConsentDenied,
                ReadOnlyMemory<byte>.Empty).ConfigureAwait(true);

            Shutdown(allowed ? 0 : 1);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Consent prompt failed: {ex.Message}", "TechSupport consent",
                MessageBoxButton.OK, MessageBoxImage.Error);
            Shutdown(2);
        }
    }
}
