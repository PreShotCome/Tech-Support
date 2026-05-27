import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  Map<String, dynamic> _settings = {};
  bool _loading = true;
  int _autonomy = 1;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final s = await ApiService.getSettings();
      if (mounted) setState(() {
        _settings = s;
        _autonomy = (s['AI_AUTONOMY_LEVEL'] as num?)?.toInt() ?? 1;
        _loading  = false;
      });
    } catch (_) { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _save(String key, dynamic value) async {
    await ApiService.updateSetting(key, value);
    _snack('Saved');
  }

  void _snack(String m) => ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(m), backgroundColor: const Color(0xFF1a1f35)));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0a0e1a),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0a0e1a),
        title: const Text('SETTINGS', style: TextStyle(
          color: Color(0xFF90a4ae), letterSpacing: 3, fontSize: 13)),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF4fc3f7)))
          : ListView(padding: const EdgeInsets.all(20), children: [

              _section('RISK MANAGEMENT'),
              _sliderTile(
                label: 'Stop Loss',
                value: (_settings['STOP_LOSS_PCT'] as num?)?.toDouble().abs() ?? 10.0,
                min: 3, max: 25,
                color: Colors.redAccent,
                display: (v) => '-${v.toStringAsFixed(0)}%',
                onChanged: (v) => _save('STOP_LOSS_PCT', -v),
              ),
              _sliderTile(
                label: 'Trailing Stop Activates At',
                value: (_settings['TRAILING_ACTIVATE_PCT'] as num?)?.toDouble() ?? 15.0,
                min: 5, max: 50,
                color: const Color(0xFFFFD700),
                display: (v) => '+${v.toStringAsFixed(0)}%',
                onChanged: (v) => _save('TRAILING_ACTIVATE_PCT', v),
              ),
              _sliderTile(
                label: 'Trailing Stop Pullback',
                value: (_settings['TRAILING_STOP_PCT'] as num?)?.toDouble() ?? 8.0,
                min: 3, max: 20,
                color: Colors.orangeAccent,
                display: (v) => '${v.toStringAsFixed(0)}% from peak',
                onChanged: (v) => _save('TRAILING_STOP_PCT', v),
              ),
              const SizedBox(height: 24),

              _section('ALLOCATION'),
              _sliderTile(
                label: 'Max Single Trade',
                value: ((_settings['MAX_SINGLE_TRADE_PCT'] as num?)?.toDouble() ?? 0.5) * 100,
                min: 10, max: 100,
                color: const Color(0xFF4fc3f7),
                display: (v) => '${v.toStringAsFixed(0)}% of buying power',
                onChanged: (v) => _save('MAX_SINGLE_TRADE_PCT', v / 100),
              ),
              _sliderTile(
                label: 'Congress Trade Size',
                value: ((_settings['CONGRESS_TRADE_ALLOCATION'] as num?)?.toDouble() ?? 0.3) * 100,
                min: 5, max: 50,
                color: const Color(0xFFb0bec5),
                display: (v) => '${v.toStringAsFixed(0)}% of buying power',
                onChanged: (v) => _save('CONGRESS_TRADE_ALLOCATION', v / 100),
              ),
              const SizedBox(height: 24),

              _section('AI AUTONOMY LEVEL'),
              _card(Column(children: [
                _autonomyOption(0, '👁  Observe Only',
                    'Analyzes and advises — never executes trades'),
                _autonomyOption(1, '💬  Suggest',
                    'Recommends trades — you confirm before execution'),
                _autonomyOption(2, '⚡  Full Autonomy',
                    'Acts on its own judgment with full permission'),
              ])),
              const SizedBox(height: 24),

              _section('ACCOUNT'),
              _card(Column(children: [
                // Signed-in user info
                if (FirebaseAuth.instance.currentUser != null) ...[
                  Row(children: [
                    CircleAvatar(
                      radius: 18,
                      backgroundColor: const Color(0xFF1A35A0),
                      backgroundImage: FirebaseAuth.instance.currentUser!.photoURL != null
                          ? NetworkImage(FirebaseAuth.instance.currentUser!.photoURL!)
                          : null,
                      child: FirebaseAuth.instance.currentUser!.photoURL == null
                          ? const Icon(Icons.person, color: Color(0xFFC9A227), size: 18)
                          : null,
                    ),
                    const SizedBox(width: 12),
                    Expanded(child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          FirebaseAuth.instance.currentUser!.displayName ??
                              FirebaseAuth.instance.currentUser!.email ?? 'User',
                          style: const TextStyle(
                              color: Colors.white, fontSize: 13,
                              fontWeight: FontWeight.bold),
                        ),
                        if (FirebaseAuth.instance.currentUser!.email != null)
                          Text(
                            FirebaseAuth.instance.currentUser!.email!,
                            style: const TextStyle(
                                color: Color(0xFFB0C4DE), fontSize: 11),
                          ),
                      ],
                    )),
                  ]),
                  const SizedBox(height: 14),
                  const Divider(color: Colors.white12),
                  const SizedBox(height: 10),
                ],
                // Sign out button
                GestureDetector(
                  onTap: () async {
                    final confirmed = await showDialog<bool>(
                      context: context,
                      builder: (ctx) => AlertDialog(
                        backgroundColor: const Color(0xFF0F2485),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16)),
                        title: const Text('Sign Out',
                            style: TextStyle(color: Colors.white)),
                        content: const Text(
                            'Are you sure you want to sign out?',
                            style: TextStyle(color: Color(0xFFB0C4DE))),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(ctx, false),
                            child: const Text('Cancel',
                                style: TextStyle(color: Color(0xFFB0C4DE))),
                          ),
                          TextButton(
                            onPressed: () => Navigator.pop(ctx, true),
                            child: const Text('Sign Out',
                                style: TextStyle(color: Colors.redAccent)),
                          ),
                        ],
                      ),
                    );
                    if (confirmed == true) await AuthService.signOut();
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        vertical: 12, horizontal: 14),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.07),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                          color: Colors.red.withOpacity(0.25)),
                    ),
                    child: const Row(children: [
                      Icon(Icons.logout, color: Colors.redAccent, size: 18),
                      SizedBox(width: 10),
                      Text('Sign Out',
                          style: TextStyle(
                              color: Colors.redAccent,
                              fontWeight: FontWeight.bold,
                              fontSize: 14)),
                    ]),
                  ),
                ),
              ])),
              const SizedBox(height: 24),

              _section('TIMING'),
              _sliderTile(
                label: 'Scan Interval',
                value: ((_settings['SCAN_INTERVAL_SECONDS'] as num?)?.toDouble() ?? 300) / 60,
                min: 1, max: 60,
                divisions: 59,
                color: const Color(0xFF4fc3f7),
                display: (v) => '${v.toStringAsFixed(0)} min',
                onChanged: (v) => _save('SCAN_INTERVAL_SECONDS', (v * 60).toInt()),
              ),
            ]),
    );
  }

  Widget _section(String t) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Text(t, style: const TextStyle(
      color: Color(0xFF90a4ae), fontSize: 11, letterSpacing: 3, fontFamily: 'monospace',
    )),
  );

  Widget _card(Widget child) => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: Colors.white.withOpacity(0.04),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: Colors.white12),
    ),
    child: child,
  );

  Widget _autonomyOption(int level, String title, String subtitle) {
    final selected = _autonomy == level;
    final colors = [Colors.blueGrey, const Color(0xFF4fc3f7), const Color(0xFFFFD700)];
    return GestureDetector(
      onTap: () async {
        setState(() => _autonomy = level);
        await _save('AI_AUTONOMY_LEVEL', level);
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: selected ? colors[level].withOpacity(0.1) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: selected ? colors[level] : Colors.white12,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(children: [
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: TextStyle(
              color: selected ? colors[level] : Colors.white70,
              fontWeight: FontWeight.bold, fontSize: 14,
            )),
            Text(subtitle, style: const TextStyle(color: Colors.white38, fontSize: 11)),
          ]),
          const Spacer(),
          if (selected) Icon(Icons.check_circle, color: colors[level], size: 20),
        ]),
      ),
    );
  }

  Widget _sliderTile({
    required String label,
    required double value,
    required double min,
    required double max,
    required Color color,
    required String Function(double) display,
    required Future<void> Function(double) onChanged,
    int? divisions,
  }) {
    double _val = value.clamp(min, max);
    return StatefulBuilder(
      builder: (ctx, setSt) => Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.04),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white12),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Text(label, style: const TextStyle(color: Colors.white70, fontSize: 13)),
            const Spacer(),
            Text(display(_val), style: TextStyle(
              color: color, fontWeight: FontWeight.bold, fontSize: 13)),
          ]),
          Slider(
            value: _val, min: min, max: max,
            divisions: divisions ?? (max - min).toInt(),
            activeColor: color,
            inactiveColor: color.withOpacity(0.2),
            onChanged: (v) => setSt(() => _val = v),
            onChangeEnd: onChanged,
          ),
        ]),
      ),
    );
  }
}
