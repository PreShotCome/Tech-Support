# CLAUDE.md — Tech-Support repo

> Read this first when starting work in this repo. Conventions, layout,
> and the load-bearing documents are below.

## What this is

A long-term thinking partner for Ian, built around four interlocking
systems:

1. **Identity** — `/IDENTITY.md` is the canonical design document. The
   model that runs the system changes over years; this file is what
   persists. Read it at the start of every session.
2. **Trading bot** — `python/trading/` + `python/scripts/`. Equal-weight
   basket rebalanced via Alpaca paper. ML side-cars live in shadow
   mode; the live trader is intentionally simple.
3. **Agent** — `python/agent/` runs the chat loop. Uses the local
   `claude` CLI (Max subscription, no API charges) by default; Ollama
   fallback. Tools registered in `python/agent/tools/`.
4. **Flutter chat app** — `flutter_app/` (this is the surface the human
   chats through). Firestore sync via the Python `firebase_bridge`.

## Stack

| Layer | Tech |
|---|---|
| Brain | Claude Opus 4.7 via `claude -p` CLI (Max plan auth). Ollama fallback. |
| Memory | Transcripts (`~/.techsupport_agent/transcripts/`), notes (`~/.techsupport_agent/notes.md`), embeddings index (fastembed, BAAI/bge-small) |
| Trading | Alpaca paper, XGBoost, Python |
| App | Flutter (web/desktop/mobile) |
| Sync | Firestore (`conversations/{userId}/messages/{messageId}`) |
| Bridge | `python -m agent.bridges.firebase_bridge` |

## Layout

```
IDENTITY.md                  # design intent — read first, every session
docs/
  bot-playbook.md            # operational lessons from prior trading work
  skills/                    # the six trading-bot skills (4 enforced, 2 reference)
  research/                  # market research that informed the trading work
python/
  agent/                     # the chat agent: brain + tools + bridges + state
  trading/                   # data, features, models, backtest, risk
  scripts/                   # CLI entry points (backtest, train, paper_runner...)
flutter_app/                 # Flutter chat surface — follows plutus-app conventions
bridge.ps1 / bridge.bat      # one-command Firebase bridge launcher
```

## Flutter conventions (matches plutus-app)

- Flat `lib/{models, screens, services}` directories. No `widgets/`,
  no `features/`, no `repositories/`.
- File naming: `snake_case.dart`, role-suffixed (`*_screen.dart`,
  `*_service.dart`). Class names PascalCase; screens end `Screen`,
  services end `Service`.
- Pubspec name: single lowercase word (`techsupport`). SDK constraint
  `>=3.3.0 <4.0.0`.
- App entrypoint: `main()` → `WidgetsFlutterBinding.ensureInitialized()`
  → `Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform)`
  → `runApp(const TechSupportApp())`. `TechSupportApp` returns one
  `MaterialApp(home: AuthGate())` — **no router package**.
- AuthGate: `StreamBuilder<User?>` on `AuthService.authStateChanges`.
- Color palette: inline `class TS { static const ... }` in `main.dart`
  (PreShotCome convention — `PC` for plutus, `TS` for tech-support).
- State sharing: top-level `ValueNotifier`s as a pub/sub bus
  (`navRequest`, `messagesChanged`). **No Riverpod / Bloc / Provider /
  go_router.** Raw `setState` for everything else.
- Backend calls (when added): `await AuthService.idToken()` as
  `Authorization: Bearer <token>`; base URL loaded from
  `SharedPreferences` in `main()`.

The one deliberate departure from plutus: this app talks to **Firestore
directly** for chat sync rather than going through an HTTP backend.
That's by design — the bridge architecture moves the agent off-device.

## Python conventions

- venv at `python/.venv/`; install with `pip install -e .[trading,agent,firebase]`.
- Trading scripts run as modules: `python -m scripts.paper_runner`.
- Agent CLI: `python -m agent.cli`.
- Bridge: `bridge.ps1` (or `bridge.bat`) from anywhere — wraps cwd,
  venv, env vars.

## Dev rules

- **Don't change IDENTITY.md without recording the change in its own
  changelog table.** That table is the actual history of the system.
- **Don't introduce a state-management package** to the Flutter app.
  Convention is `setState` + `ValueNotifier`. Adding Riverpod breaks
  consistency with plutus and adds nothing this app needs.
- **Trading: every order goes through `validate_trade`.** Block = block.
  No override path. See `docs/skills/02-pre-trade-validation.md`.
- **Decisions go to logs.** `decisions.jsonl` for trading,
  transcripts for chat. The logs are the audit trail and the input
  to the growth loop.
- **Never commit `firebase-key.json`** or any service-account JSON.
  Already in `.gitignore`. Client-side configs
  (`firebase_options.dart`, `google-services.json`,
  `GoogleService-Info.plist`) are safe to commit.

## When extending

- **New agent tool:** one file in `python/agent/tools/` exposing a
  `register(registry)` function. Then add a single import + entry to
  `python/agent/tools/_all.py` (the canonical module list). cli.py,
  scripts/dump_brain.py, and tools/system.py's introspection all read
  from there — no other edits. Schema is JSON Schema, handler is a
  Python function. See `tools/system.py` for the smallest example.
- **New Flutter screen:** one file in `lib/screens/`, add to
  `MainShell`'s `tabs` list or push via `Navigator.push`.
- **New trading strategy:** subclass `Strategy` in
  `trading/strategies/base.py`. Run through `walkforward.py` before
  even considering deployment.

## Long-term

The repo started as a remote-support tool (Windows agent for screen
capture + input injection — still present under `src/`). It pivoted
into a trading bot, then absorbed an agent layer, now a Flutter chat
surface. The Windows agent code is dormant but not removed — it's
part of the project's history and may come back as a tool the agent
operates.

The shape worth holding in mind: **IDENTITY.md is the spine; the
agent and its tools are the limbs; trading is one capability; chat is
the surface; transcripts + notes + identity are the memory.** Future
capabilities slot in as new tools without re-architecting.
