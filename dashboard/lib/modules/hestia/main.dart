// Hestia — Flutter port (Phase 1, minimal).
//
// The original Hestia is React Native with photo upload, room/container CRUD,
// household creation, tagging, etc. This Phase 1 port covers the read path
// (login → see your household's inventory → tap an item to view detail) so
// the dashboard can prove the architecture works against the same Firestore
// data. The original RN app keeps running in parallel; full write-path
// parity comes in a follow-up.
//
// Firestore schema (matches original):
//   users/{uid}                          — UserDoc { householdId }
//   households/{hid}                     — Household
//   households/{hid}/rooms/{id}
//   households/{hid}/containers/{id}
//   households/{hid}/items/{id}

import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

// Hestia color palette — HC per PreShotCome convention.
class HC {
  static const background = Color(0xFF13110F);
  static const surface    = Color(0xFF1F1A14);
  static const card       = Color(0xFF2A2218);
  static const accent     = Color(0xFFFFA070); // warm terracotta
  static const accentSoft = Color(0xFFFFC9A0);
  static const sage       = Color(0xFFB0A090);
  static const danger     = Color(0xFFE57373);
}

FirebaseAuth get _auth =>
    FirebaseAuth.instanceFor(app: Firebase.app('hestia'));
FirebaseFirestore get _db =>
    FirebaseFirestore.instanceFor(app: Firebase.app('hestia'));

class HestiaApp extends StatelessWidget {
  const HestiaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Hestia',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: HC.background,
        colorScheme: const ColorScheme.dark(
          primary: HC.accent,
          secondary: HC.accentSoft,
          surface: HC.surface,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: HC.background,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: HC.sage, fontSize: 13, letterSpacing: 3,
            fontWeight: FontWeight.bold,
          ),
        ),
        cardTheme: CardTheme(
          color: HC.card,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      home: const _HestiaAuthGate(),
    );
  }
}

class _HestiaAuthGate extends StatelessWidget {
  const _HestiaAuthGate();

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: _auth.authStateChanges(),
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator(color: HC.accent)),
          );
        }
        return snap.data == null ? const _LoginScreen() : const _InventoryHome();
      },
    );
  }
}

// ── Login ────────────────────────────────────────────────────────────────

class _LoginScreen extends StatefulWidget {
  const _LoginScreen();
  @override
  State<_LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<_LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  String? _error;
  bool _busy = false;

  Future<void> _signIn() async {
    setState(() { _error = null; _busy = true; });
    try {
      await _auth.signInWithEmailAndPassword(
        email: _email.text.trim(),
        password: _password.text,
      );
    } on FirebaseAuthException catch (e) {
      setState(() => _error = e.message ?? e.code);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('HESTIA')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Sign in to your household.',
                  style: TextStyle(color: HC.sage, fontSize: 14)),
              const SizedBox(height: 24),
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                style: const TextStyle(color: Colors.white),
                decoration: const InputDecoration(
                  labelText: 'Email',
                  filled: true,
                  fillColor: HC.surface,
                  border: OutlineInputBorder(borderSide: BorderSide.none),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _password,
                obscureText: true,
                style: const TextStyle(color: Colors.white),
                decoration: const InputDecoration(
                  labelText: 'Password',
                  filled: true,
                  fillColor: HC.surface,
                  border: OutlineInputBorder(borderSide: BorderSide.none),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: HC.danger, fontSize: 13)),
              ],
              const SizedBox(height: 24),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: HC.accent, foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                onPressed: _busy ? null : _signIn,
                child: Text(_busy ? 'Signing in…' : 'SIGN IN',
                    style: const TextStyle(letterSpacing: 2, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(height: 16),
              const Text(
                'New users: sign up in the original Hestia app first, then return here.',
                style: TextStyle(color: HC.sage, fontSize: 11),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Inventory home ───────────────────────────────────────────────────────

class _InventoryHome extends StatefulWidget {
  const _InventoryHome();
  @override
  State<_InventoryHome> createState() => _InventoryHomeState();
}

class _InventoryHomeState extends State<_InventoryHome> {
  String? _householdId;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadHousehold();
  }

  Future<void> _loadHousehold() async {
    final uid = _auth.currentUser!.uid;
    final snap = await _db.collection('users').doc(uid).get();
    setState(() {
      _householdId = snap.data()?['householdId'] as String?;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator(color: HC.accent)));
    }
    if (_householdId == null) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('HESTIA'),
          actions: [
            IconButton(icon: const Icon(Icons.logout), onPressed: () => _auth.signOut()),
          ],
        ),
        body: const Padding(
          padding: EdgeInsets.all(32),
          child: Center(
            child: Text(
              'No household yet. Open the original Hestia app to create or join one — the dashboard will pick it up automatically.',
              style: TextStyle(color: HC.sage), textAlign: TextAlign.center,
            ),
          ),
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('INVENTORY'),
        actions: [
          IconButton(icon: const Icon(Icons.logout), onPressed: () => _auth.signOut()),
        ],
      ),
      body: StreamBuilder<QuerySnapshot>(
        stream: _db.collection('households').doc(_householdId)
            .collection('items').snapshots(),
        builder: (context, snap) {
          if (!snap.hasData) {
            return const Center(child: CircularProgressIndicator(color: HC.accent));
          }
          final docs = snap.data!.docs;
          if (docs.isEmpty) {
            return const Center(
              child: Text('No items yet.', style: TextStyle(color: HC.sage)),
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: docs.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) {
              final d = docs[i];
              final data = d.data() as Map<String, dynamic>;
              return Card(
                child: ListTile(
                  leading: const Icon(Icons.inventory_2_outlined, color: HC.accent),
                  title: Text(data['name'] ?? '—', style: const TextStyle(color: Colors.white)),
                  subtitle: Text(
                    'qty ${data['quantity'] ?? 0}'
                    '${(data['notes'] as String?)?.isNotEmpty == true ? '  ·  ${data['notes']}' : ''}',
                    style: const TextStyle(color: HC.sage, fontSize: 12),
                  ),
                  onTap: () {
                    Navigator.push(context, MaterialPageRoute(
                      builder: (_) => _ItemDetail(id: d.id, householdId: _householdId!, data: data),
                    ));
                  },
                ),
              );
            },
          );
        },
      ),
    );
  }
}

// ── Item detail (read-only Phase 1) ──────────────────────────────────────

class _ItemDetail extends StatelessWidget {
  final String id;
  final String householdId;
  final Map<String, dynamic> data;
  const _ItemDetail({required this.id, required this.householdId, required this.data});

  @override
  Widget build(BuildContext context) {
    final name = data['name'] ?? '—';
    final notes = data['notes'] as String? ?? '';
    final qty = data['quantity'] ?? 0;
    final tags = (data['tags'] as List?)?.cast<String>() ?? const [];
    return Scaffold(
      appBar: AppBar(title: Text(name.toString().toUpperCase())),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(name, style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('Quantity: $qty', style: const TextStyle(color: HC.sage)),
            if (notes.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Text('NOTES', style: TextStyle(color: HC.sage, fontSize: 11, letterSpacing: 2)),
              const SizedBox(height: 4),
              Text(notes, style: const TextStyle(color: Colors.white)),
            ],
            if (tags.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Text('TAGS', style: TextStyle(color: HC.sage, fontSize: 11, letterSpacing: 2)),
              const SizedBox(height: 6),
              Wrap(
                spacing: 6, runSpacing: 6,
                children: tags.map((t) => Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: HC.accent.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(t, style: const TextStyle(color: HC.accentSoft, fontSize: 12)),
                )).toList(),
              ),
            ],
            const SizedBox(height: 32),
            const Text(
              'Edit, photo upload, and room/container management remain in the original Hestia app for Phase 1.',
              style: TextStyle(color: HC.sage, fontSize: 11),
            ),
          ],
        ),
      ),
    );
  }
}
