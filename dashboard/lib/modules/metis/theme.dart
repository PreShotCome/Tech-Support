import 'package:flutter/material.dart';

/// Metis palette — cyan accents on deep indigo, monospace-forward UI.
class MC {
  static const bg        = Color(0xFF0D0B1F);
  static const surface   = Color(0xFF15132E);
  static const card      = Color(0xFF1C1A3A);
  static const cardHi    = Color(0xFF252247);
  static const border    = Color(0xFF2E2B55);
  static const cyan      = Color(0xFF4FE3D8);
  static const cyanDim   = Color(0xFF2C7E7A);
  static const text      = Color(0xFFE7E7F2);
  static const muted     = Color(0xFF8B88B4);
  static const amber     = Color(0xFFF5B544);
  static const red       = Color(0xFFFF6B7A);
  static const green     = Color(0xFF54D98C);
}

const _mono = 'monospace';

ThemeData buildMetisTheme() {
  return ThemeData(
    useMaterial3: true,
    fontFamily: _mono,
    scaffoldBackgroundColor: MC.bg,
    colorScheme: const ColorScheme.dark(
      primary: MC.cyan,
      secondary: MC.amber,
      surface: MC.surface,
      error: MC.red,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: MC.bg,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontFamily: _mono,
        color: MC.cyan,
        fontSize: 16,
        fontWeight: FontWeight.bold,
        letterSpacing: 2,
      ),
      iconTheme: IconThemeData(color: MC.cyan),
    ),
    dividerColor: MC.border,
    snackBarTheme: const SnackBarThemeData(
      backgroundColor: MC.card,
      contentTextStyle: TextStyle(fontFamily: _mono, color: MC.text),
      behavior: SnackBarBehavior.floating,
    ),
  );
}
