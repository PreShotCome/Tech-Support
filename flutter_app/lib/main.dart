// Entry point + App widget + AuthGate + MainShell + TS palette.
// Following plutus-app's convention: flat lib/ structure, no router, no
// Riverpod/Bloc/Provider. State sharing via top-level ValueNotifiers.

import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'firebase_options.dart';
import 'screens/login_screen.dart';
import 'screens/main_shell.dart';

// ──────────────────────────────────────────────────────────────────────────
// Color palette — `TS` per PreShotCome convention (PC = plutus, TS = ours).
// One source of truth; all screens read from this.

class TS {
  static const background  = Color(0xFF0B0F14);   // near-black blue
  static const surface     = Color(0xFF141B22);   // card
  static const surfaceAlt  = Color(0xFF1B232C);
  static const accent      = Color(0xFFB2A4FF);   // soft lavender — peer / thinking
  static const accentSoft  = Color(0xFF8276D6);
  static const gold        = Color(0xFFE6B85C);   // attention / state
  static const sage        = Color(0xFFA0B0A6);   // secondary text
  static const danger      = Color(0xFFE57373);
  static const success     = Color(0xFF7BC47F);
}

// ──────────────────────────────────────────────────────────────────────────
// Top-level ValueNotifiers — the pub/sub bus across screens.
// Screens add listeners in initState, remove in dispose. This mirrors
// plutus's navRequest / *Changed pattern.

final ValueNotifier<String?> navRequest = ValueNotifier<String?>(null);
final ValueNotifier<int> messagesChanged = ValueNotifier<int>(0);

// ──────────────────────────────────────────────────────────────────────────

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  runApp(const TechSupportApp());
}

class TechSupportApp extends StatelessWidget {
  const TechSupportApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TechSupport',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      home: const AuthGate(),
    );
  }

  ThemeData _buildTheme() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: TS.background,
      colorScheme: const ColorScheme.dark(
        primary: TS.accent,
        secondary: TS.gold,
        surface: TS.surface,
        onPrimary: Colors.black,
        onSecondary: Colors.black,
        onSurface: Colors.white,
        error: TS.danger,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: TS.background,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: TS.sage,
          fontSize: 13,
          fontWeight: FontWeight.w600,
          letterSpacing: 1.2,
        ),
      ),
      cardTheme: CardTheme(
        color: TS.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: TS.surfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: TS.surface,
        indicatorColor: TS.accent.withOpacity(0.18),
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
        ),
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────────────────
// AuthGate — gates the app on auth state. Plutus pattern verbatim.

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator(color: TS.accent)),
          );
        }
        if (snapshot.data == null) {
          return const LoginScreen();
        }
        return MainShell(user: snapshot.data!);
      },
    );
  }
}
