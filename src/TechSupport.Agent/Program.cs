using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Hosting.WindowsServices;
using Serilog;
using TechSupport.Agent;
using TechSupport.Agent.Capture;
using TechSupport.Agent.Consent;
using TechSupport.Agent.Input;
using TechSupport.Agent.Net;

// Fallback crash logger — runs before any framework / DI is up so we
// see errors even if Serilog fails to initialize.
var crashLogPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
    "TechSupport", "agent-crash.log");

void WriteCrash(string source, Exception? ex)
{
    try
    {
        Directory.CreateDirectory(Path.GetDirectoryName(crashLogPath)!);
        File.AppendAllText(crashLogPath,
            $"[{DateTimeOffset.Now:O}] {source}\n{ex}\n\n");
    }
    catch { /* never throw inside the crash handler */ }
}

AppDomain.CurrentDomain.UnhandledException += (_, e) =>
    WriteCrash("AppDomain.UnhandledException", e.ExceptionObject as Exception);
TaskScheduler.UnobservedTaskException += (_, e) =>
{
    WriteCrash("TaskScheduler.UnobservedTaskException", e.Exception);
    e.SetObserved();
};

WriteCrash("Startup", null);

var builder = Host.CreateApplicationBuilder(args);

// Force appsettings.json to be loaded from the binary directory rather
// than the current working directory — when launched via Start-Process
// without -WorkingDirectory those differ and Serilog config goes missing.
builder.Configuration.SetBasePath(AppContext.BaseDirectory);
builder.Configuration.AddJsonFile("appsettings.json", optional: true, reloadOnChange: true);

builder.Services.AddOptions<AgentOptions>()
    .Bind(builder.Configuration.GetSection(AgentOptions.SectionName))
    .ValidateOnStart();

builder.Services.AddWindowsService(o => o.ServiceName = "TechSupport.Agent");

builder.Services.AddSingleton<IScreenCapture, DxgiScreenCapture>();
builder.Services.AddSingleton<IInputInjector, Win32InputInjector>();
builder.Services.AddSingleton<SessionRegistry>();
builder.Services.AddSingleton<ConsentBroker>();
builder.Services.AddHostedService<AgentService>();
builder.Services.AddHostedService<LanListener>();

builder.Services.AddSerilog((sp, lc) => lc
    .ReadFrom.Configuration(builder.Configuration));

var host = builder.Build();
await host.RunAsync();
