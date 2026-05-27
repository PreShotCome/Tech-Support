import 'package:flutter/material.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';

import 'screens/email_screen.dart';
import 'screens/history_screen.dart';
import 'screens/reminders_screen.dart';
import 'screens/settings_screen.dart';
import 'services/foreground_service.dart';
import 'services/notification_service.dart';
import 'services/reminder_repository.dart';
import 'services/settings_store.dart';
import 'theme.dart';

// main() stripped — module loaded via dashboard entry.dart
class MetisApp extends StatelessWidget {
  const MetisApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Metis',
      debugShowCheckedModeBanner: false,
      theme: buildMetisTheme(),
      home: const MainShell(),
    );
  }
}

/// Fixed four-tab shell: Reminders · Email · History · Settings.
class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  static const _screens = [
    RemindersScreen(),
    EmailScreen(),
    HistoryScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return WithForegroundTask(
      child: Scaffold(
        body: IndexedStack(index: _index, children: _screens),
        bottomNavigationBar: NavigationBarTheme(
          data: NavigationBarThemeData(
            backgroundColor: MC.surface,
            indicatorColor: MC.cyan.withOpacity(0.18),
            labelTextStyle: WidgetStateProperty.all(
              const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 10,
                  fontWeight: FontWeight.bold),
            ),
          ),
          child: NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.notifications_none, color: MC.muted),
                selectedIcon: Icon(Icons.notifications, color: MC.cyan),
                label: 'Reminders',
              ),
              NavigationDestination(
                icon: Icon(Icons.mail_outline, color: MC.muted),
                selectedIcon: Icon(Icons.mail, color: MC.cyan),
                label: 'Email',
              ),
              NavigationDestination(
                icon: Icon(Icons.history, color: MC.muted),
                selectedIcon: Icon(Icons.history, color: MC.cyan),
                label: 'History',
              ),
              NavigationDestination(
                icon: Icon(Icons.settings_outlined, color: MC.muted),
                selectedIcon: Icon(Icons.settings, color: MC.cyan),
                label: 'Settings',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
