import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'firebase_options.dart';
import 'chat_screen.dart';

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
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6750A4),
          brightness: Brightness.dark,
        ),
      ),
      home: const AuthGate(),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        if (snapshot.data == null) {
          return const SignInScreen();
        }
        return ChatScreen(userId: snapshot.data!.uid);
      },
    );
  }
}

class SignInScreen extends StatelessWidget {
  const SignInScreen({super.key});

  Future<void> _signInAnonymously() async {
    await FirebaseAuth.instance.signInAnonymously();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('TechSupport', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w300)),
            const SizedBox(height: 32),
            FilledButton.icon(
              onPressed: _signInAnonymously,
              icon: const Icon(Icons.login),
              label: const Text('Continue'),
            ),
          ],
        ),
      ),
    );
  }
}
