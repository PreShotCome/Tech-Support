# TechSupport Chat — Flutter + Firebase

A real chat UI for the TechSupport agent. Flutter on the front;
Firestore in the middle as a sync layer; the Python `firebase_bridge`
on the back end running the agent. The same conversation appears on
your phone, your desktop, and a tab in your browser — all writing to
the same Firestore collection.

## Architecture

```
   Flutter UI  ──── write user msg ────►  Firestore
       ▲                                       │
       │                                       │
       └── subscribe (live)                    ▼
              ◄─── write assistant msg ── firebase_bridge.py
                                               │
                                               ▼
                                       Agent.chat()  ──► tools (trading,
                                                              memory, etc.)
```

The Flutter app does nothing but UI + Firestore I/O. The brain lives
in `python/agent/`. The bridge connects them.

## One-time setup

### 1. Create a Firebase project

1. Go to https://console.firebase.google.com/ and click **Add project**.
   Name it whatever — `techsupport-chat` works.
2. In the project, enable **Firestore Database** (start in production
   mode is fine; we'll set security rules below).
3. Enable **Authentication → Anonymous** (the simplest sign-in flow;
   you can add Google / Apple later).

### 2. Generate the Flutter `firebase_options.dart`

```bash
# Install the FlutterFire CLI once:
dart pub global activate flutterfire_cli

# In flutter_app/:
flutterfire configure
```

That command will list your projects, ask which platforms to register
(pick Android / iOS / web — whichever you want to deploy to), and
write a real `firebase_options.dart` over the placeholder.

### 3. Set Firestore security rules

In Firebase Console → Firestore → Rules, paste this. It restricts each
user to only their own messages collection:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /conversations/{userId}/messages/{messageId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

### 4. Generate a service account for the Python bridge

1. Firebase Console → Project Settings → Service Accounts
2. Click **Generate new private key** → download the JSON.
3. Save it somewhere safe on your machine, e.g.
   `C:\src\Tech-Support\firebase-key.json`.
   **Do not commit it to git** — `.gitignore` covers `firebase-key.json`.

### 5. Run the bridge

```powershell
# Activate the venv:
cd C:\src\Tech-Support\python
.\.venv\Scripts\activate

# Install Firebase support:
pip install -e .[firebase]

# Set credentials + project ID:
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\src\Tech-Support\firebase-key.json"
$env:FIREBASE_PROJECT_ID = "your-project-id"  # from Firebase Console

# Start the bridge — leave this running:
python -m agent.bridges.firebase_bridge
```

### 6. Run the Flutter app

```bash
cd flutter_app
flutter pub get
flutter run        # picks an attached device
# or
flutter run -d chrome   # web
flutter run -d windows  # Windows desktop
```

Sign in (anonymous, one tap), type a message, the bridge processes it
in seconds, the response appears.

## What you get

- **Same conversation across devices.** Open the app on your phone,
  continue on desktop later. Firestore is the source of truth.
- **Same brain across surfaces.** CLI and chat app share the same
  Python `Agent`, same tools, same notes, same transcripts.
- **All the safety + trading tools.** Anything the CLI can do, the
  chat app can do — ask "what's my portfolio" from your phone and
  it runs through `validate_trade` / `reconcile_positions` / etc.

## Distribution

For Android: `flutter build apk` or `flutter build appbundle` →
publish to Play Store, or sideload the APK.

For iOS: `flutter build ipa` → TestFlight.

For web: `flutter build web` → deploy `build/web/` to Firebase Hosting
(one command: `firebase deploy --only hosting`).

The bridge process needs to be running somewhere. Three options:
1. **Local**: leave it running on your PC. Cheapest.
2. **Always-on cloud VM**: small DigitalOcean / Hetzner box for ~$5/mo.
3. **Cloud Run / Functions**: scale-to-zero, billed per request.

Start with option 1 to validate; move to a small VM once you're
chatting from your phone regularly and don't want your PC to be the
single point of failure.

## What's NOT here yet

- Push notifications. Add Firebase Cloud Messaging if you want pings
  when the bridge has finished an async task.
- Multi-user support. The bridge spawns one Agent per `userId` but
  the underlying notes/transcripts are shared globally. For real
  multi-user, scope those per-user too.
- Voice input/output. Add `speech_to_text` and `flutter_tts` packages.

These are reasonable next steps once the basic loop is working.
