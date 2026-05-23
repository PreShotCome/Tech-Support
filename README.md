# TechSupport

A Windows-native remote-support tool built for technicians who actually
do this work for a living. Two pieces:

- **Agent** — a Windows service that runs on the end-user's PC. Provides
  unattended access via DXGI screen capture and `SendInput` injection.
- **Console** — a WPF dashboard for the technician. Saved customers,
  quick-connect by host or pairing code, a clean Mica-themed remote view.

The point of difference is the technician workflow. Existing tools
treat every connection as a one-off "enter the 9-digit code" exchange.
This treats the customer as the first-class object: saved connections,
session history, notes, fast reconnect.

## Status

v0 — local skeleton. Works on a LAN with a direct TCP connection between
agent and console. Frames are uncompressed BGRA, fine for development;
v1 will swap in H.264 via Media Foundation. Relay / NAT traversal is
designed for but not yet implemented.

## Layout

```
src/
  TechSupport.Shared/   Wire protocol, framing, session crypto
  TechSupport.Agent/    Windows service: DXGI capture, SendInput, TCP listener
  TechSupport.Console/  WPF technician dashboard (Fluent / Mica)
scripts/
  install-agent.ps1     Installs the agent as a Windows service
docs/
  architecture.md       How the pieces fit together
  roadmap.md            What's next: relay, H.264, consent UI, MSI
```

## Build

Requires .NET 8 SDK on Windows 10 1809 or later.

```powershell
dotnet build TechSupport.sln -c Release
```

## Run (development, LAN-only)

1. On the end-user PC, run the agent in the foreground:
   ```powershell
   dotnet run --project src\TechSupport.Agent -c Release
   ```
   The agent prints its pairing code (e.g. `amber-frost-417`) and starts
   the LAN listener on port 7022.

2. On the technician PC, run the console:
   ```powershell
   dotnet run --project src\TechSupport.Console -c Release
   ```
   Enter the agent's IP in the **Quick connect** field and click
   **Connect**.

## Install agent as a service

```powershell
.\scripts\install-agent.ps1
```

Uninstall with `-Uninstall`. The script must run elevated.

## What this is not (yet)

- Not internet-routable on its own — relay is in `docs/roadmap.md`.
- Not encoded — frames are raw BGRA, so you want a fast LAN.
- Not signed — no MSI or code signature yet, so SmartScreen will warn.
- Not multi-monitor — first display only in v0.

## License

TBD — see LICENSE before shipping.
