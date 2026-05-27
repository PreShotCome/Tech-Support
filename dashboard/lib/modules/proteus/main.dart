import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'screens/dashboard_screen.dart';
import 'screens/history_screen.dart';
import 'screens/controls_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/login_screen.dart';
import 'widgets/star_field.dart';

// main() stripped — module loaded via dashboard entry.dart
// ── Proteus brand colours ────────────────────────────────────────────────────
class ProteusColors {
  // Blues
  static const background   = Color(0xFF040A22); // near-black ocean
  static const surface      = Color(0xFF0B1A6B); // deep royal blue
  static const surfaceCard  = Color(0xFF0F2485); // lifted blue for cards
  static const royalBlue    = Color(0xFF1A35A0); // mid blue for UI elements

  // Golds
  static const gold         = Color(0xFFC9A227); // rich metallic gold (primary)
  static const goldBright   = Color(0xFFF0C040); // shimmer highlight
  static const goldDim      = Color(0xFF8A6A10); // shadow / depth

  // Text
  static const textPrimary  = Color(0xFFFFFFFF);
  static const textSecond   = Color(0xFFB0C4DE); // steel blue-white
}

class TradingBotApp extends StatelessWidget {
  const TradingBotApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Proteus',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: ProteusColors.background,
        colorScheme: const ColorScheme.dark(
          primary:   ProteusColors.gold,
          secondary: ProteusColors.goldBright,
          surface:   ProteusColors.surface,
        ),
        fontFamily: 'monospace',
        appBarTheme: const AppBarTheme(
          backgroundColor: ProteusColors.background,
          foregroundColor: ProteusColors.gold,
          elevation: 0,
        ),
        dividerColor: ProteusColors.royalBlue,
        cardColor: ProteusColors.surfaceCard,
      ),
      home: const AuthWrapper(),
    );
  }
}

// ── Auth wrapper — routes to login or app based on Firebase auth state ────────
class AuthWrapper extends StatelessWidget {
  const AuthWrapper({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) {
        // Still connecting to Firebase
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            backgroundColor: Color(0xFF040A22),
            body: Center(
              child: CircularProgressIndicator(color: Color(0xFFC9A227)),
            ),
          );
        }
        // Logged in → show app
        if (snapshot.hasData) return const MainShell();
        // Logged out → show login
        return const LoginScreen();
      },
    );
  }
}

class MainShell extends StatefulWidget {
  const MainShell({super.key});
  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  final _screens = const [
    DashboardScreen(),
    HistoryScreen(),
    ControlsScreen(),
    SettingsScreen(),
    ChatScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return StarField(
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: IndexedStack(index: _index, children: _screens),
        bottomNavigationBar: Container(
          decoration: BoxDecoration(
            color: ProteusColors.surface,
            border: Border(top: BorderSide(color: ProteusColors.gold.withOpacity(0.2))),
          ),
          child: BottomNavigationBar(
            currentIndex: _index,
            onTap: (i) => setState(() => _index = i),
            backgroundColor: Colors.transparent,
            selectedItemColor: ProteusColors.gold,
            unselectedItemColor: ProteusColors.textSecond.withOpacity(0.5),
            type: BottomNavigationBarType.fixed,
            showSelectedLabels: true,
            showUnselectedLabels: true,
            selectedLabelStyle: const TextStyle(fontSize: 10, letterSpacing: 1),
            unselectedLabelStyle: const TextStyle(fontSize: 10),
            items: const [
              BottomNavigationBarItem(
                  icon: Icon(Icons.dashboard_outlined),
                  activeIcon: Icon(Icons.dashboard),
                  label: 'PORTFOLIO'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.history_outlined),
                  activeIcon: Icon(Icons.history),
                  label: 'HISTORY'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.tune_outlined),
                  activeIcon: Icon(Icons.tune),
                  label: 'CONTROL'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.settings_outlined),
                  activeIcon: Icon(Icons.settings),
                  label: 'SETTINGS'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.smart_toy_outlined),
                  activeIcon: Icon(Icons.smart_toy),
                  label: 'AI'),
            ],
          ),
        ),
      ),
    );
  }
}
