// MainShell — post-auth root. Just the chat screen now; the
// NavigationBar was dropped once it became clear one tab + a
// "Chat" label was pure noise. If/when a second screen lands,
// the navRequest ValueNotifier + IndexedStack pattern from plutus
// is the path back.

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

class MainShell extends StatelessWidget {
  final User user;
  const MainShell({super.key, required this.user});

  @override
  Widget build(BuildContext context) {
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
      body: ChatScreen(userId: user.uid),
    );
  }
}
