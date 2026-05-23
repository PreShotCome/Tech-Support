using System.Diagnostics;
using System.Runtime.Versioning;
using Microsoft.Extensions.Logging;
using Vortice.Direct3D;
using Vortice.Direct3D11;
using Vortice.DXGI;

namespace TechSupport.Agent.Capture;

/// <summary>
/// Screen capture via the DXGI Desktop Duplication API. This is the
/// supported high-FPS path on Windows 8.1+ and what every modern remote
/// access tool uses. Falls back to GDI BitBlt only if DXGI initialization
/// fails (e.g. on a session that has no GPU adapter visible).
/// </summary>
[SupportedOSPlatform("windows6.2")]
public sealed class DxgiScreenCapture : IScreenCapture
{
    private readonly ILogger<DxgiScreenCapture> _log;
    private readonly Stopwatch _clock = Stopwatch.StartNew();

    private IDXGIAdapter1? _adapter;
    private ID3D11Device? _device;
    private ID3D11DeviceContext? _context;
    private IDXGIOutputDuplication? _duplication;
    private ID3D11Texture2D? _stagingTexture;
    private OutputDescription _outputDesc;
    private bool _frameAcquired;
    private bool _firstFrame = true;

    public int Width { get; private set; }
    public int Height { get; private set; }
    public int DisplayIndex { get; private set; }

    public DxgiScreenCapture(ILogger<DxgiScreenCapture> log) => _log = log;

    public void Initialize(int displayIndex)
    {
        DisplayIndex = displayIndex;

        var factoryResult = DXGI.CreateDXGIFactory1<IDXGIFactory1>(out var factory);
        if (factoryResult.Failure)
            throw new InvalidOperationException($"CreateDXGIFactory1 failed: {factoryResult}");

        using (factory)
        {
            if (factory.EnumAdapters1(0, out _adapter).Failure || _adapter is null)
                throw new InvalidOperationException("No DXGI adapter found.");
        }

        var featureLevels = new[]
        {
            FeatureLevel.Level_11_1,
            FeatureLevel.Level_11_0,
            FeatureLevel.Level_10_1,
        };

        D3D11.D3D11CreateDevice(
            _adapter,
            DriverType.Unknown,
            DeviceCreationFlags.BgraSupport,
            featureLevels,
            out _device,
            out _context).CheckError();

        if (_adapter.EnumOutputs(displayIndex, out var output).Failure)
            throw new InvalidOperationException($"Display index {displayIndex} not found.");

        using (output)
        {
            var output1 = output.QueryInterface<IDXGIOutput1>();
            _outputDesc = output1.Description;
            _duplication = output1.DuplicateOutput(_device);
            output1.Dispose();
        }

        Width = _outputDesc.DesktopCoordinates.Right - _outputDesc.DesktopCoordinates.Left;
        Height = _outputDesc.DesktopCoordinates.Bottom - _outputDesc.DesktopCoordinates.Top;

        var stagingDesc = new Texture2DDescription
        {
            Width = (uint)Width,
            Height = (uint)Height,
            MipLevels = 1,
            ArraySize = 1,
            Format = Format.B8G8R8A8_UNorm,
            SampleDescription = new SampleDescription(1, 0),
            Usage = ResourceUsage.Staging,
            BindFlags = BindFlags.None,
            CPUAccessFlags = CpuAccessFlags.Read,
            MiscFlags = ResourceOptionFlags.None,
        };
        _stagingTexture = _device.CreateTexture2D(stagingDesc);

        _log.LogInformation(
            "DXGI capture initialized: display {Index} {Width}x{Height}",
            displayIndex, Width, Height);
    }

    public bool TryAcquireFrame(int timeoutMs, out CapturedFrame frame)
    {
        frame = default;
        if (_duplication is null || _device is null || _context is null || _stagingTexture is null)
            throw new InvalidOperationException("Capture not initialized.");

        if (_frameAcquired) ReleaseFrame();

        var hr = _duplication.AcquireNextFrame(
            (uint)timeoutMs,
            out _,
            out var resource);

        if (hr.Code == unchecked((int)0x887A0027)) // DXGI_ERROR_WAIT_TIMEOUT
            return false;

        hr.CheckError();
        _frameAcquired = true;

        using (resource)
        {
            using var sourceTexture = resource.QueryInterface<ID3D11Texture2D>();
            _context.CopyResource(_stagingTexture, sourceTexture);
        }

        var mapped = _context.Map(_stagingTexture, 0, MapMode.Read, Vortice.Direct3D11.MapFlags.None);

        var isKey = _firstFrame;
        _firstFrame = false;

        frame = new CapturedFrame(
            mapped.DataPointer,
            Width,
            Height,
            (int)mapped.RowPitch,
            isKey,
            _clock.Elapsed.Ticks / (TimeSpan.TicksPerMillisecond / 1000));

        return true;
    }

    public void ReleaseFrame()
    {
        if (!_frameAcquired) return;
        try
        {
            _context?.Unmap(_stagingTexture!, 0);
            _duplication?.ReleaseFrame();
        }
        catch (Exception ex)
        {
            _log.LogDebug(ex, "ReleaseFrame swallowed");
        }
        finally
        {
            _frameAcquired = false;
        }
    }

    public void Dispose()
    {
        ReleaseFrame();
        _stagingTexture?.Dispose();
        _duplication?.Dispose();
        _context?.Dispose();
        _device?.Dispose();
        _adapter?.Dispose();
    }
}
