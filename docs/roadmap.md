# Roadmap

## v0 — done

- Solution + 3 projects
- DXGI Desktop Duplication capture
- `SendInput` mouse / keyboard / wheel injection (virtual-desktop coords)
- Length-prefixed binary protocol, JSON control plane
- LAN-direct TCP listener (port 7022)
- WPF technician dashboard with saved connections, quick-connect, remote view

## v0.5 — done (this commit)

- Console restructured around `NavigationView` with Home, Customers,
  History, Settings pages.
- **Customer record UI** (the differentiator) — master-detail view
  with contact fields, freeform notes, a list of machines per customer,
  and per-customer session history.
- JSON-backed `CustomerStore` in `%APPDATA%\TechSupport` with
  debounced writes.
- Session history tracked automatically on connect / disconnect.
- **Consent prompt** as a separate WPF exe (`TechSupport.ConsentPrompt`)
  launched by the agent over a per-request named pipe. Agent refuses
  to start the session if the user denies or ignores the prompt.

## v1 — make it useful

1. **H.264 encoding via Media Foundation.** Raw BGRA at 1080p30 is
   ~250 MB/s — fine on a LAN, useless on the internet. Encode in the
   agent using `MFCreateSinkWriterFromURL` with a hardware codec; decode
   in the console using `MediaFoundationReader` or a managed wrapper.
2. **Damage-rectangle delta frames.** DXGI reports dirty rects per
   frame — only ship changed regions. Halves bandwidth even before H.264.
3. ~~**Consent UI.**~~ Done in v0.5. Still TODO when the agent runs as
   the SYSTEM service: replace `Process.Start` with `CreateProcessAsUser`
   so the prompt appears in the interactive console session rather than
   session 0. Until then, the prompt only works when the agent runs as
   the logged-in user.
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
