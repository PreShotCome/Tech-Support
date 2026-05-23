using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Hosting.WindowsServices;
using Serilog;
using TechSupport.Agent;
using TechSupport.Agent.Capture;
using TechSupport.Agent.Input;
using TechSupport.Agent.Net;

var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddOptions<AgentOptions>()
    .Bind(builder.Configuration.GetSection(AgentOptions.SectionName))
    .ValidateOnStart();

builder.Services.AddWindowsService(o => o.ServiceName = "TechSupport.Agent");

builder.Services.AddSingleton<IScreenCapture, DxgiScreenCapture>();
builder.Services.AddSingleton<IInputInjector, Win32InputInjector>();
builder.Services.AddSingleton<SessionRegistry>();
builder.Services.AddHostedService<AgentService>();
builder.Services.AddHostedService<LanListener>();

builder.Services.AddSerilog((sp, lc) => lc
    .ReadFrom.Configuration(builder.Configuration));

var host = builder.Build();
await host.RunAsync();
