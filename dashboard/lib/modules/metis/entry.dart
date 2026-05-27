// Metis module entry. Replicates the original main()'s init sequence
// (settings, notifications, foreground task config, reminders) then renders
// the module's MetisApp.

import 'package:flutter/material.dart';
import 'main.dart' show MetisApp;
import 'services/foreground_service.dart';
import 'services/notification_service.dart';
import 'services/reminder_repository.dart';
import 'services/settings_store.dart';

class MetisEntry extends StatefulWidget {
  const MetisEntry({super.key});
  @override
  State<MetisEntry> createState() => _MetisEntryState();
}

class _MetisEntryState extends State<MetisEntry> {
  Future<void>? _bootstrap;

  @override
  void initState() {
    super.initState();
    _bootstrap = _init();
  }

  Future<void> _init() async {
    await settings.load();
    await NotificationService.init();
    ForegroundService.configure();
    await reminders.load();
    if (settings.foregroundEnabled) {
      await ForegroundService.start();
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<void>(
      future: _bootstrap,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        return const MetisApp();
      },
    );
  }
}
