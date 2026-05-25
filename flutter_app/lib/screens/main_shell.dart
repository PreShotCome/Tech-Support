// MainShell — post-auth root. Plutus pattern: NavigationBar +
// IndexedStack. Only one tab today (Chat). Adding tabs later means
// adding a screen file and one entry below; no router change needed.

import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';

import '../main.dart';            // TS palette + navRequest
import '../services/auth_service.dart';
// Conditional import: dart:html on web, stub elsewhere. Lets the
// brain button stay buildable on mobile/desktop without pulling a
// dependency just to open one URL.
import '../services/brain_launcher_stub.dart'
    if (dart.library.html) '../services/brain_launcher.dart';
import 'chat_screen.dart';

class MainShell extends StatefulWidget {
  final User user;
  const MainShell({super.key, required this.user});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    navRequest.addListener(_onNavRequest);
  }

  @override
  void dispose() {
    navRequest.removeListener(_onNavRequest);
    super.dispose();
  }

  void _onNavRequest() {
    final id = navRequest.value;
    if (id == null) return;
    final idx = _tabIndexFor(id);
    if (idx != null && idx != _tab) setState(() => _tab = idx);
    navRequest.value = null;
  }

  int? _tabIndexFor(String id) {
    switch (id) {
      case 'chat':
        return 0;
      default:
        return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final tabs = <Widget>[
      ChatScreen(userId: widget.user.uid),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('TECHSUPPORT'),
        actions: [
          IconButton(
            icon: const Icon(Icons.hub_outlined, size: 20),
            color: TS.sage,
            tooltip: 'Brain',
            onPressed: openBrain,
          ),
          IconButton(
            icon: const Icon(Icons.logout, size: 20),
            color: TS.sage,
            tooltip: 'Sign out',
            onPressed: () => AuthService.signOut(),
          ),
        ],
      ),
      body: IndexedStack(index: _tab, children: tabs),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: 'Chat',
          ),
        ],
      ),
    );
  }
}
