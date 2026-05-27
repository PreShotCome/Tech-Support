// PreShotCome Dashboard — entry point.
// Initializes one default Firebase app (Trading-Bot / woohoo-ad450) plus
// three named apps (plutus, theo, hestia). Each module addresses its own
// Firebase project via Firebase.app('<name>') so per-app auth state and
// Firestore streams stay isolated.

import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:timezone/data/latest_all.dart' as tz;

import 'firebase_options_multi.dart';
import 'shell/dashboard_home.dart';

// Brand palette — neutral chrome around the per-module screens.
class DC {
  static const background = Color(0xFF0A0E14);
  static const surface    = Color(0xFF141A22);
  static const accent     = Color(0xFFB2A4FF);
  static const sage       = Color(0xFFA0B0A6);
  static const gold       = Color(0xFFE6B85C);
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  tz.initializeTimeZones();

  // Default app — Trading-Bot's woohoo-ad450 (because firebase_messaging
  // attaches to the default app on Android).
  await Firebase.initializeApp(options: tradingBotOptions);

  // Named apps — addressed via Firebase.app('<name>').
  await Firebase.initializeApp(name: 'plutus', options: plutusOptions);
  await Firebase.initializeApp(name: 'theo',   options: theoOptions);
  await Firebase.initializeApp(name: 'hestia', options: hestiaOptions);

  runApp(const DashboardApp());
}

class DashboardApp extends StatelessWidget {
  const DashboardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PreShotCome',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: DC.background,
        colorScheme: const ColorScheme.dark(
          primary: DC.accent,
          secondary: DC.gold,
          surface: DC.surface,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: DC.background,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: DC.sage, fontSize: 13, letterSpacing: 3,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      home: const DashboardHome(),
    );
  }
}
