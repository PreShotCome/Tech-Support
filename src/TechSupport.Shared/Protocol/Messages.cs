using System.Text.Json;
using System.Text.Json.Serialization;

namespace TechSupport.Shared.Protocol;

public static class JsonMessages
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public static byte[] Encode<T>(T value) =>
        JsonSerializer.SerializeToUtf8Bytes(value, Options);

    public static T Decode<T>(ReadOnlySpan<byte> payload) =>
        JsonSerializer.Deserialize<T>(payload, Options)
        ?? throw new InvalidDataException($"Failed to decode {typeof(T).Name}");
}

public record HelloMessage(
    string AgentId,
    string MachineName,
    string OsVersion,
    string AgentVersion,
    string[] Capabilities,
    string? TechnicianName = null,
    string? Reason = null);

public record HelloAckMessage(
    string SessionId,
    string ServerVersion,
    bool RequireConsent);

public record SessionRequestMessage(
    string TechnicianId,
    string TechnicianName,
    string Reason);

public record ConsentPromptMessage(
    string TechnicianName,
    string Reason,
    int TimeoutSeconds);

public record DisplayInfoMessage(
    int Width,
    int Height,
    int DpiX,
    int DpiY,
    int DisplayIndex,
    int DisplayCount);

public record FrameHeader(
    int Width,
    int Height,
    int Stride,
    long TimestampUs,
    bool IsKeyFrame,
    string Codec);

public record CursorUpdateMessage(
    int X,
    int Y,
    bool Visible,
    byte[]? PngOverride);

public record MouseMoveMessage(int X, int Y);

public record MouseButtonMessage(
    int X,
    int Y,
    MouseButton Button,
    bool Pressed);

public record MouseWheelMessage(int X, int Y, int DeltaX, int DeltaY);

public record KeyEventMessage(int VirtualKey, int ScanCode, bool Pressed, bool Extended);

public enum MouseButton : byte
{
    Left = 0,
    Right = 1,
    Middle = 2,
    XButton1 = 3,
    XButton2 = 4,
}

public record AgentStatsMessage(
    double CpuPercent,
    double MemoryMb,
    long BytesSent,
    long BytesReceived,
    int FrameRate);
