import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

class AuthService {
  static final _auth   = FirebaseAuth.instanceFor(app: Firebase.app('plutus'));
  static final _google = GoogleSignIn();

  static Stream<User?> get authStateChanges => _auth.authStateChanges();
  static User? get currentUser => _auth.currentUser;

  /// Fresh Firebase ID token for backend requests (auto-refreshed by the SDK).
  static Future<String?> idToken() async => _auth.currentUser?.getIdToken();

  static Future<UserCredential> signInWithEmail(String email, String password) =>
      _auth.signInWithEmailAndPassword(email: email.trim(), password: password);

  static Future<UserCredential> createAccount(String email, String password) =>
      _auth.createUserWithEmailAndPassword(email: email.trim(), password: password);

  static Future<void> sendPasswordReset(String email) =>
      _auth.sendPasswordResetEmail(email: email.trim());

  static Future<UserCredential?> signInWithGoogle() async {
    final user = await _google.signIn();
    if (user == null) return null;
    final auth = await user.authentication;
    return _auth.signInWithCredential(GoogleAuthProvider.credential(
      accessToken: auth.accessToken, idToken: auth.idToken));
  }

  static Future<UserCredential> signInWithApple() async {
    final credential = await SignInWithApple.getAppleIDCredential(
      scopes: [
        AppleIDAuthorizationScopes.email,
        AppleIDAuthorizationScopes.fullName,
      ],
    );
    final oauth = OAuthProvider('apple.com').credential(
      idToken: credential.identityToken,
      accessToken: credential.authorizationCode,
    );
    return _auth.signInWithCredential(oauth);
  }

  static Future<void> signOut() async {
    await Future.wait([_auth.signOut(), _google.signOut()]);
  }

  static String friendlyError(FirebaseAuthException e) {
    switch (e.code) {
      case 'user-not-found':       return 'No account found with that email.';
      case 'wrong-password':       return 'Incorrect password.';
      case 'invalid-credential':   return 'Incorrect email or password.';
      case 'email-already-in-use': return 'Account already exists with that email.';
      case 'weak-password':        return 'Password must be at least 6 characters.';
      case 'invalid-email':        return 'Please enter a valid email address.';
      case 'too-many-requests':    return 'Too many attempts. Try again later.';
      case 'network-request-failed': return 'Network error. Check your connection.';
      default:                     return e.message ?? 'Authentication failed.';
    }
  }
}
