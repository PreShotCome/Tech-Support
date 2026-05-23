namespace TechSupport.Agent;

public sealed class AgentOptions
{
    public const string SectionName = "Agent";

    public string RelayUri { get; set; } = "wss://relay.techsupport.local/agent";
    public string ListenHost { get; set; } = "0.0.0.0";
    public int ListenPort { get; set; } = 7022;
    public bool EnableLanDirect { get; set; } = true;
    public bool EnableHttpControl { get; set; } = true;
    public int HttpControlPort { get; set; } = 7023;
    public int DefaultFrameRate { get; set; } = 30;
    public bool RequireConsent { get; set; } = true;
    public int ConsentTimeoutSeconds { get; set; } = 30;
}
