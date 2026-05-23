using TechSupport.Shared.Protocol;

namespace TechSupport.Agent.Input;

public interface IInputInjector
{
    void MoveMouse(int x, int y);
    void Button(int x, int y, MouseButton button, bool pressed);
    void Wheel(int x, int y, int deltaX, int deltaY);
    void Key(int virtualKey, int scanCode, bool pressed, bool extended);
}
