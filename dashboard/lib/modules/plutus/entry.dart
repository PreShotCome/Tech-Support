// Plutus module entry. Wraps the module's existing PlutuApp.
// Internal Navigator.push calls work because PlutuApp's MaterialApp creates
// its own Navigator below the dashboard's outer Navigator.

import 'package:flutter/material.dart';
import 'main.dart' show PlutuApp;
import 'services/api_service.dart';

class PlutusEntry extends StatefulWidget {
  const PlutusEntry({super.key});
  @override
  State<PlutusEntry> createState() => _PlutusEntryState();
}

class _PlutusEntryState extends State<PlutusEntry> {
  Future<void>? _bootstrap;

  @override
  void initState() {
    super.initState();
    // Plutus's original main() ran ApiService.loadBaseUrl() before runApp.
    // Replicate that here so the API client has its base URL configured.
    _bootstrap = ApiService.loadBaseUrl();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<void>(
      future: _bootstrap,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        return const PlutuApp();
      },
    );
  }
}
