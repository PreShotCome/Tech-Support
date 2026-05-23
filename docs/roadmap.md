# Roadmap

## v0 — done (this commit)

- Solution + 3 projects
- DXGI Desktop Duplication capture
- `SendInput` mouse / keyboard / wheel injection (virtual-desktop coords)
- Length-prefixed binary protocol, JSON control plane
- LAN-direct TCP listener (port 7022)
- WPF technician dashboard with saved connections, quick-connect, remote view

## v1 — make it useful

1. **H.264 encoding via Media Foundation.** Raw BGRA at 1080p30 is
   ~250 MB/s — fine on a LAN, useless on the internet. Encode in the
   agent using `MFCreateSinkWriterFromURL` with a hardware codec; decode
   in the console using `MediaFoundationReader` or a managed wrapper.
2. **Damage-rectangle delta frames.** DXGI reports dirty rects per
   frame — only ship changed regions. Halves bandwidth even before H.264.
3. **Consent UI.** A separate small WPF app (running in the user's
   session, not the SYSTEM service) that pops up "Allow technician
   {Name} to view your screen?" and writes the answer to a named pipe
   the service reads. The service must NOT inject input until this
   returns yes.
4. **Relay.** ASP.NET Core service exposing two WebSocket endpoints
   (`/agent`, `/console`) and a pairing lookup. Bridges bytes between
   agent and console when direct connect isn't possible. Authenticates
   the agent by HMAC of the pairing code.
5. **TLS on direct.** Self-signed cert generated on first agent start,
   stored in `LocalMachine\My`. Console pins by SHA-256 fingerprint
   shown alongside the pairing code at install time.
6. **Multi-monitor.** Send `DisplayInfo` listing all outputs; let the
   technician switch between them.

## v2 — the things existing tools lose

- Customer record. Notes, last session, common issues, attached files.
- Session recording. Optional MP4 capture of the session for compliance.
- Built-in chat. Lightweight text channel during the session.
- Quick scripts. Technician-side library of PowerShell snippets to
  push and run on the agent (with explicit consent and a log entry).
- File transfer. Drag-and-drop folder onto the remote view.

## v3 — ship it

- Code-sign agent + console.
- MSI installer (WiX) that registers the service and pins firewall
  exceptions.
- Auto-update channel for both agent and console.
- Crash reporting (Sentry or self-hosted).
- Licensing server.
