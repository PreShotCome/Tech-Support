# Architecture

## Three components

```
+--------------------+              +--------------------+
|  Technician PC     |              |  End-user PC       |
|                    |              |                    |
|  TechSupport       |  TCP / TLS   |  TechSupport       |
|  .Console (WPF)    | <----------> |  .Agent (service)  |
|                    |              |                    |
+--------------------+              +--------------------+
          ^                                   ^
          |                                   |
          |          (v1, not yet)            |
          +-----> [Relay (ASP.NET Core)] <----+
                  - pairing-code lookup
                  - WebSocket muxer
                  - TURN/STUN for P2P
```

For v0 the technician dials the agent directly over the LAN (port 7022).
The relay design exists in `roadmap.md` and is what enables
internet-routable sessions and unattended access from anywhere.

## Agent

Hosts:
- **DXGI Desktop Duplication** capture loop. Creates a Direct3D 11
  device, opens the primary output, and on every frame copies the
  desktop texture to a CPU-readable staging texture for serialization.
  This is hardware-accelerated and used by every modern remote tool.
- **SendInput** injection. Mouse coordinates are converted to virtual-
  desktop normalized absolute coordinates (0..65535) so multi-monitor
  setups work correctly.
- **LAN listener** on TCP/7022. Each accepted connection runs a
  `SessionHandler` that exchanges `Hello/HelloAck/DisplayInfo` then
  pumps frames out and input messages in.
- **Session registry** so the agent always knows who's connected.

## Console

A WPF app using WPF-UI's Fluent / Mica styling. MVVM via
`CommunityToolkit.Mvvm`. Main panes:

- Left rail: saved connections + quick-connect.
- Right pane: `RemoteDesktopView` — a `WriteableBitmap` updated from
  decoded frames, with mouse and keyboard events forwarded to the agent
  via `AgentConnection`.

## Wire protocol

Length-prefixed binary framing (see `FrameCodec.cs`):

```
[u32 length] [u8 type] [payload]
```

For control messages the payload is UTF-8 JSON. For video frames it's a
JSON header followed by the raw pixel buffer of `stride * height` bytes
(BGRA in v0).

Message types live in `MessageType.cs`. The protocol is intentionally
JSON-on-the-wire for the control plane so we can read frames in
Wireshark during development and switch payloads to MessagePack later
without re-thinking the framing.

## Security model (v0 → v1)

- v0: LAN only, no TLS. **Do not expose port 7022 to the internet.**
- v1:
  - TLS on the agent listener with a self-signed cert pinned by the
    pairing-code fingerprint.
  - Explicit consent prompt on the agent unless the customer has marked
    the technician as trusted (unattended).
  - Action log written to the agent's Windows event log: every input
    injection, every file transfer (when we add it).
