// Per-module health screen. Verifies each Firebase project initialized,
// resolves its current auth user (if any), and does one trivial Firestore
// read against the project to confirm credentials and network reach.

import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

import '../main.dart' show DC;

class DebugScreen extends StatefulWidget {
  const DebugScreen({super.key});

  @override
  State<DebugScreen> createState() => _DebugScreenState();
}

class _ModuleStatus {
  final String label;
  final String firebaseAppName; // '__default__' for default app
  bool initOk = false;
  String? userId;
  bool readOk = false;
  String? error;
  _ModuleStatus(this.label, this.firebaseAppName);
}

class _DebugScreenState extends State<DebugScreen> {
  final _statuses = [
    _ModuleStatus('Proteus (woohoo-ad450, default)', '[DEFAULT]'),
    _ModuleStatus('Plutus (plutus-f7e90)', 'plutus'),
    _ModuleStatus('Theo (data-55089)', 'theo'),
    _ModuleStatus('Hestia (hestia-fbc49)', 'hestia'),
  ];
  bool _running = false;

  @override
  void initState() {
    super.initState();
    _run();
  }

  Future<void> _run() async {
    setState(() => _running = true);
    for (final s in _statuses) {
      try {
        final app = s.firebaseAppName == '[DEFAULT]'
            ? Firebase.app()
            : Firebase.app(s.firebaseAppName);
        s.initOk = true;
        s.userId = FirebaseAuth.instanceFor(app: app).currentUser?.uid;
        // Try a tiny Firestore read — limit 1 doc from a probe collection.
        // If the project has no such collection it returns an empty snapshot
        // (still counts as success); only network/permission failures throw.
        final snap = await FirebaseFirestore.instanceFor(app: app)
            .collection('_dashboard_probe')
            .limit(1)
            .get();
        s.readOk = snap.metadata.isFromCache == false || snap.docs.isEmpty;
      } catch (e) {
        s.error = e.toString();
      }
      if (mounted) setState(() {});
    }
    setState(() => _running = false);
  }

  Widget _row(_ModuleStatus s) {
    return Card(
      color: DC.surface,
      child: ListTile(
        title: Text(s.label, style: const TextStyle(color: Colors.white)),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 6),
            _check('Initialized', s.initOk),
            _check('Auth resolved', s.userId != null,
                detail: s.userId == null ? 'signed out' : 'uid: ${s.userId}'),
            _check('Firestore read', s.readOk),
            if (s.error != null)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(s.error!,
                    style: const TextStyle(color: Colors.redAccent, fontSize: 11)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _check(String label, bool ok, {String? detail}) {
    return Padding(
      padding: const EdgeInsets.only(top: 2),
      child: Row(
        children: [
          Icon(ok ? Icons.check_circle : Icons.radio_button_unchecked,
              color: ok ? Colors.greenAccent : DC.sage, size: 14),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(color: DC.sage, fontSize: 12)),
          if (detail != null) ...[
            const SizedBox(width: 6),
            Expanded(
              child: Text(detail,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: DC.sage, fontSize: 11)),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('MODULE STATUS'),
        actions: [
          IconButton(
            icon: Icon(_running ? Icons.hourglass_empty : Icons.refresh),
            onPressed: _running ? null : _run,
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: _statuses.map(_row).toList(),
      ),
    );
  }
}
