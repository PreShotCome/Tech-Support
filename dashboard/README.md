# PreShotCome Dashboard

A single Flutter app that opens all the user-facing apps in one place. Each
module retains its own Firebase project (via named Firebase apps), its own
backend connections, and its own UI theme — so live Firestore streams,
push notifications, and API calls continue to work exactly as they did in
each module's standalone app.

| Tile | Source repo | Firebase project |
|---|---|---|
| Plutus | preshotcome/plutus-app | plutus-f7e90 (named `plutus`) |
| Proteus | preshotcome/trading-bot-app | woohoo-ad450 (**default**) |
| Metis | preshotcome/Metis | none |
| Theo | preshotcome/Tech-Support (`flutter_app/`) | data-55089 (named `theo`) |
| Hestia | preshotcome/Hestia (Flutter port — read-only Phase 1) | hestia-fbc49 (named `hestia`) |
| Restore Drill | preshotcome/restore-drill | PWA via WebView |

The original repos are **not modified**. Their apps keep working in parallel
during dashboard verification.

## Bootstrap (run once on your machine)

This remote dev environment has no Flutter SDK, so the Android/iOS native
scaffolding (`android/`, `ios/`, `MainActivity.kt`, gradle files) isn't
checked in. Generate it locally:

```bash
cd Tech-Support/dashboard
flutter create . --project-name dashboard --org com.preshotcome --platforms=android
```

`flutter create` is non-destructive — it adds missing files but preserves the
existing `lib/`, `pubspec.yaml`, `assets/`, and `android/app/src/main/AndroidManifest.xml`.

Then drop in:

1. **`android/app/google-services.json`** — download from the Firebase
   console for the `woohoo-ad450` project. This is the default Firebase app
   that backs `FirebaseMessaging` for Proteus push notifications.
2. **Update `android/app/build.gradle`** to apply the Google services plugin:
   ```gradle
   apply plugin: 'com.google.gms.google-services'
   ```
   and add the classpath in `android/build.gradle`:
   ```gradle
   classpath 'com.google.gms:google-services:4.4.2'
   ```

3. **Set the application ID** in `android/app/build.gradle.kts` to
   `com.preshotcome.dashboard` (or whatever you registered the Android
   app under in the Firebase console).

4. **Theo Android appId** — `lib/firebase_options_multi.dart` currently has
   the web appId for the `data-55089` project. Add an Android app to the
   `data-55089` Firebase project (package `com.preshotcome.dashboard`) and
   replace the `appId` value in `theoOptions` with the real Android appId.

Then:

```bash
flutter pub get
flutter run -d <android-device>
```

## Verifying the modules

The dashboard's home screen has a small status icon (top-right) that opens
**MODULE STATUS** — four rows, one per Firebase project, each checking:

- ✓ Firebase app initialized
- ✓ Auth state resolved (signed in / out)
- ✓ Firestore read against the project succeeded

If any row is red, that module's Firebase config is wrong. Common causes:
the Android appId in `firebase_options_multi.dart` doesn't match the
Firebase project's registered Android app, or `google-services.json` is
missing from `android/app/`.

Once all four rows are green:

1. Tap **Plutus** → sign in to plutus-f7e90 → confirm transactions load
   from the Railway backend.
2. Tap **Proteus** → sign in to woohoo-ad450 → confirm portfolio loads,
   and trigger a trade alert to confirm push notifications fire.
3. Tap **Metis** → confirm reminders fire from background.
4. Tap **Theo** → sign in to data-55089 → confirm chat history syncs.
5. Tap **Hestia** → sign in to hestia-fbc49 → confirm your household's
   inventory items appear.
6. Tap **Restore Drill** → the WebView loads the PWA URL configured in
   `lib/modules/restore_drill/webview_screen.dart` (currently a
   placeholder — update before shipping).

## Architecture notes

- **Multi-Firebase** — `lib/main.dart` initializes one default app
  (`woohoo-ad450`) and three named apps (`plutus`, `theo`, `hestia`).
  Each module's `FirebaseAuth.instance` / `FirebaseFirestore.instance`
  calls were sed-rewritten to `FirebaseAuth.instanceFor(app: Firebase.app('<name>'))`,
  so auth state and Firestore streams stay isolated per project.
- **Nested MaterialApps** — each module's tile pushes a route whose
  child is the module's original `MaterialApp` (with its own theme +
  Navigator), so the module's internal `Navigator.push` calls keep
  working unchanged. System back returns to the dashboard home.
- **Modules** live at `lib/modules/<name>/`. Each module's `entry.dart`
  is the public widget the shell instantiates. The module's original
  `main.dart` is preserved as a library file with `void main()` removed.
- **Hestia** is a partial Flutter port (read-only). Use the original
  Hestia app for photo capture, room/container CRUD, and household
  creation; the dashboard picks up the same Firestore data automatically.

## What's not in Phase 1

- iOS build (Android-only). To add iOS later: add a `GoogleService-Info.plist`
  per Firebase project, register iOS bundle IDs, and reconcile the Podfile.
- Full Hestia parity (writes, photos, household management, tags).
- Hardened cleartext-traffic rules (currently allowed app-wide for the
  Proteus HTTP backend — should be narrowed via `network_security_config`).
- Crashlytics (single-default-app only, not wired).
