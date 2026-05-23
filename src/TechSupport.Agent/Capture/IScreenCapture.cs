namespace TechSupport.Agent.Capture;

public interface IScreenCapture : IDisposable
{
    int Width { get; }
    int Height { get; }
    int DisplayIndex { get; }

    void Initialize(int displayIndex);

    /// <summary>
    /// Wait for the next frame from the desktop duplication API.
    /// Returns false on timeout (no screen change in the window).
    /// </summary>
    bool TryAcquireFrame(int timeoutMs, out CapturedFrame frame);

    void ReleaseFrame();
}

public readonly record struct CapturedFrame(
    IntPtr Bgra,
    int Width,
    int Height,
    int Stride,
    bool IsKeyFrame,
    long TimestampUs);
