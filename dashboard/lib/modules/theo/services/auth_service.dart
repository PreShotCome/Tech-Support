// Auth service — static-method class wrapping FirebaseAuth.
// Mirrors plutus-app/lib/services/auth_service.dart shape so future
// sessions and code review feel identical.
//
// Providers wired:
//   - Anonymous (default entry, single tap)
//   - Email/password
//   - Google (stub — uncomment + configure OAuth client ID to enable)
//   - Apple   (stub — same)
//
// Backend ID token helper included for parity with plutus, even though
// the chat layer uses Firestore directly. Future tools that hit a
// custom backend can pass `await AuthService.idToken()` as the bearer.

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';

class AuthService {
  static FirebaseAuth get _auth => FirebaseAuth.instanceFor(app: Firebase.app('theo'));

  static User? get currentUser => _auth.currentUser;

  static Stream<User?> get authStateChanges => _auth.authStateChanges();

  // ── Sign-in flows ────────────────────────────────────────────────

  static Future<UserCredential> signInAnonymously() {
    return _auth.signInAnonymously();
  }

  static Future<UserCredential> signInWithEmail(String email, String password) {
    return _auth.signInWithEmailAndPassword(
      email: email.trim(),
      password: password,
    );
  }

  static Future<UserCredential> signUpWithEmail(String email, String password) {
    return _auth.createUserWithEmailAndPassword(
      email: email.trim(),
      password: password,
    );
  }

  // Google / Apple — wire the actual SDK calls when you set up OAuth.
  // Imports left out so the app builds without those configs in place.

  // ── Misc ─────────────────────────────────────────────────────────

  static Future<void> signOut() => _auth.signOut();

  /// Bearer token for calling a custom backend. Null when signed out.
  static Future<String?> idToken({bool forceRefresh = false}) async {
    final u = _auth.currentUser;
    if (u == null) return null;
    return u.getIdToken(forceRefresh);
  }

  /// Maps Firebase error codes to human-readable strings for SnackBars.
  static String friendlyError(Object e) {
    if (e is FirebaseAuthException) {
      switch (e.code) {
        case 'invalid-email':
          return 'That email address looks malformed.';
        case 'user-disabled':
          return 'This account has been disabled.';
        case 'user-not-found':
          return 'No account exists for that email.';
        case 'wrong-password':
        case 'invalid-credential':
          return 'Wrong email or password.';
        case 'email-already-in-use':
          return 'An account with that email already exists.';
        case 'weak-password':
          return 'Pick a stronger password (8+ characters).';
        case 'network-request-failed':
          return 'Network unreachable. Check your connection and try again.';
        case 'too-many-requests':
          return 'Too many attempts. Wait a moment and try again.';
        case 'operation-not-allowed':
          return 'That sign-in method is not enabled in Firebase.';
        default:
          return e.message ?? 'Auth error: ${e.code}';
      }
    }
    return e.toString();
  }
}
