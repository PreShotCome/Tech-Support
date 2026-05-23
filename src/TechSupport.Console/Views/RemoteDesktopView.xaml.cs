using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using TechSupport.Console.ViewModels;
using SharedMouseButton = TechSupport.Shared.Protocol.MouseButton;

namespace TechSupport.Console.Views;

public partial class RemoteDesktopView : UserControl
{
    public RemoteDesktopView()
    {
        InitializeComponent();
        Loaded += (_, _) => Focus();
        KeyDown += OnKeyDown;
        KeyUp += OnKeyUp;
    }

    private SessionViewModel? Session => DataContext as SessionViewModel;

    private (int x, int y)? ToRemote(MouseEventArgs e)
    {
        if (Session is null) return null;
        var pos = e.GetPosition(FrameImage);
        var w = FrameImage.ActualWidth;
        var h = FrameImage.ActualHeight;
        if (w <= 0 || h <= 0) return null;
        var rx = (int)(pos.X / w * Session.DisplayWidth);
        var ry = (int)(pos.Y / h * Session.DisplayHeight);
        return (rx, ry);
    }

    private async void OnMouseMove(object sender, MouseEventArgs e)
    {
        if (ToRemote(e) is not var (rx, ry)) return;
        if (Session is null) return;
        await Session.SendMouseMoveAsync(rx, ry);
    }

    private async void OnMouseDown(object sender, MouseButtonEventArgs e)
    {
        if (ToRemote(e) is not var (rx, ry)) return;
        if (Session is null) return;
        await Session.SendMouseButtonAsync(rx, ry, MapButton(e.ChangedButton), pressed: true);
    }

    private async void OnMouseUp(object sender, MouseButtonEventArgs e)
    {
        if (ToRemote(e) is not var (rx, ry)) return;
        if (Session is null) return;
        await Session.SendMouseButtonAsync(rx, ry, MapButton(e.ChangedButton), pressed: false);
    }

    private async void OnMouseWheel(object sender, MouseWheelEventArgs e)
    {
        if (ToRemote(e) is not var (rx, ry)) return;
        if (Session is null) return;
        await Session.SendWheelAsync(rx, ry, 0, e.Delta);
    }

    private async void OnKeyDown(object sender, KeyEventArgs e)
    {
        if (Session is null) return;
        var vk = KeyInterop.VirtualKeyFromKey(e.Key);
        var sc = (int)e.ScanCode();
        await Session.SendKeyAsync(vk, sc, pressed: true, extended: false);
        e.Handled = true;
    }

    private async void OnKeyUp(object sender, KeyEventArgs e)
    {
        if (Session is null) return;
        var vk = KeyInterop.VirtualKeyFromKey(e.Key);
        var sc = (int)e.ScanCode();
        await Session.SendKeyAsync(vk, sc, pressed: false, extended: false);
        e.Handled = true;
    }

    private static SharedMouseButton MapButton(MouseButton button) => button switch
    {
        System.Windows.Input.MouseButton.Left => SharedMouseButton.Left,
        System.Windows.Input.MouseButton.Right => SharedMouseButton.Right,
        System.Windows.Input.MouseButton.Middle => SharedMouseButton.Middle,
        System.Windows.Input.MouseButton.XButton1 => SharedMouseButton.XButton1,
        System.Windows.Input.MouseButton.XButton2 => SharedMouseButton.XButton2,
        _ => SharedMouseButton.Left,
    };
}

internal static class KeyEventArgsExtensions
{
    public static uint ScanCode(this System.Windows.Input.KeyEventArgs e)
    {
        var vk = (uint)KeyInterop.VirtualKeyFromKey(e.Key);
        return MapVirtualKey(vk, 0 /* MAPVK_VK_TO_VSC */);
    }

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern uint MapVirtualKey(uint uCode, uint uMapType);
}
