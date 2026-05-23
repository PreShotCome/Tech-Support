namespace TechSupport.Shared.Protocol;

public enum MessageType : byte
{
    Unknown = 0,

    // Control plane
    Hello = 1,
    HelloAck = 2,
    Ping = 3,
    Pong = 4,
    Bye = 5,

    // Session lifecycle
    SessionRequest = 10,
    SessionAccept = 11,
    SessionReject = 12,
    ConsentPrompt = 13,
    ConsentGranted = 14,
    ConsentDenied = 15,

    // Video / capture
    FrameKey = 20,
    FrameDelta = 21,
    CursorUpdate = 22,
    DisplayInfo = 23,

    // Input injection (technician -> agent)
    MouseMove = 30,
    MouseButton = 31,
    MouseWheel = 32,
    KeyEvent = 33,
    ClipboardSync = 34,

    // Telemetry
    AgentStats = 40,
}
