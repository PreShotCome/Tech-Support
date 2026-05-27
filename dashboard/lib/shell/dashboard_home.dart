// Home screen — a grid of app tiles. Tapping a tile pushes a nested
// Navigator route hosting that module's entry widget. The nested Navigator
// keeps each module's internal Navigator.push/pop calls working as-is.

import 'package:flutter/material.dart';

import '../main.dart' show DC;
import '../modules/plutus/entry.dart';
import '../modules/proteus/entry.dart';
import '../modules/metis/entry.dart';
import '../modules/theo/entry.dart';
import '../modules/hestia/entry.dart';
import '../modules/restore_drill/webview_screen.dart';
import 'debug_screen.dart';

class _Tile {
  final String label;
  final String subtitle;
  final IconData icon;
  final Color color;
  final Widget Function() build;
  const _Tile(this.label, this.subtitle, this.icon, this.color, this.build);
}

class DashboardHome extends StatelessWidget {
  const DashboardHome({super.key});

  static final _tiles = <_Tile>[
    _Tile('Plutus',       'Money',       Icons.account_balance_wallet,
        const Color(0xFFFFB7C5), () => const PlutusEntry()),
    _Tile('Proteus',      'Trading',     Icons.show_chart,
        const Color(0xFFC9A227), () => const ProteusEntry()),
    _Tile('Metis',        'Reminders',   Icons.notifications_active,
        const Color(0xFF66E0FF), () => const MetisEntry()),
    _Tile('Theo',         'Chat',        Icons.psychology,
        const Color(0xFFB2A4FF), () => const TheoEntry()),
    _Tile('Hestia',       'Inventory',   Icons.inventory_2,
        const Color(0xFFFFA070), () => const HestiaEntry()),
    _Tile('Restore Drill','Backup',      Icons.backup,
        const Color(0xFF7BC47F), () => const RestoreDrillWebView()),
  ];

  void _open(BuildContext context, _Tile tile) {
    // Each module returns its own MaterialApp (its theme + Navigator), so we
    // just push it as a route on the dashboard's Navigator.
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => tile.build()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PRESHOTCOME'),
        actions: [
          IconButton(
            icon: const Icon(Icons.health_and_safety_outlined, color: DC.sage),
            tooltip: 'Module status',
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => const DebugScreen(),
            )),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: GridView.count(
            crossAxisCount: 2,
            mainAxisSpacing: 14,
            crossAxisSpacing: 14,
            children: _tiles.map((t) => _TileCard(tile: t, onTap: () => _open(context, t))).toList(),
          ),
        ),
      ),
    );
  }
}

class _TileCard extends StatelessWidget {
  final _Tile tile;
  final VoidCallback onTap;
  const _TileCard({required this.tile, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: DC.surface,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: tile.color.withOpacity(0.22)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 46, height: 46,
                decoration: BoxDecoration(
                  color: tile.color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(tile.icon, color: tile.color, size: 26),
              ),
              const SizedBox(height: 16),
              Text(tile.label,
                  style: const TextStyle(
                      color: Colors.white, fontSize: 18,
                      fontWeight: FontWeight.bold, letterSpacing: 1)),
              const SizedBox(height: 4),
              Text(tile.subtitle.toUpperCase(),
                  style: const TextStyle(
                      color: DC.sage, fontSize: 10, letterSpacing: 2)),
            ],
          ),
        ),
      ),
    );
  }
}
