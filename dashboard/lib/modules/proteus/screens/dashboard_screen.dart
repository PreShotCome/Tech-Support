import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../widgets/star_field.dart';

enum SortMode { value, gainPct, symbol, assetType }

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  Timer? _timer;
  SortMode _sort = SortMode.value;
  final _usd = NumberFormat.currency(symbol: '\$');

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _load());
  }

  @override
  void dispose() { _timer?.cancel(); super.dispose(); }

  Future<void> _load() async {
    try {
      final d = await ApiService.getPortfolio();
      if (mounted) setState(() { _data = d; _loading = false; });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  List _sortedPositions() {
    final positions = List.from(_data?['positions'] as List? ?? []);
    switch (_sort) {
      case SortMode.value:
        positions.sort((a, b) => (b['equity'] as num).compareTo(a['equity'] as num));
      case SortMode.gainPct:
        positions.sort((a, b) => (b['return_pct'] as num).compareTo(a['return_pct'] as num));
      case SortMode.symbol:
        positions.sort((a, b) => (a['symbol'] as String).compareTo(b['symbol'] as String));
      case SortMode.assetType:
        positions.sort((a, b) => (a['asset_type'] as String).compareTo(b['asset_type'] as String));
    }
    return positions;
  }

  @override
  Widget build(BuildContext context) {
    final total  = _data?['total_value'] as double? ?? 0;
    final bp     = _data?['buying_power'] as double? ?? 0;
    final paused = _data?['bot_paused'] as bool? ?? false;

    return StarField(
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: _loading
            ? const Center(child: CircularProgressIndicator(color: Color(0xFF4fc3f7)))
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 60, 20, 20),
                  children: [
                    // Header row
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('PORTFOLIO', style: TextStyle(
                          color: Color(0xFF90a4ae), fontSize: 12,
                          letterSpacing: 3, fontFamily: 'monospace',
                        )),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: paused
                                ? Colors.red.withOpacity(0.2)
                                : const Color(0xFF00b894).withOpacity(0.2),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                              color: paused ? Colors.red : const Color(0xFF00b894)),
                          ),
                          child: Text(
                            paused ? '⏸ PAUSED' : '● LIVE',
                            style: TextStyle(
                              color: paused ? Colors.red : const Color(0xFF00b894),
                              fontSize: 11, fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),

                    // Total value
                    Text(
                      _usd.format(total),
                      style: const TextStyle(
                        color: Color(0xFFFFD700), fontSize: 48,
                        fontWeight: FontWeight.bold, letterSpacing: -1,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text('Total Portfolio Value',
                        style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13)),
                    const SizedBox(height: 24),

                    // Stats row
                    Row(children: [
                      _statCard('Buying Power', _usd.format(bp), const Color(0xFF4fc3f7)),
                      const SizedBox(width: 12),
                      _statCard('Positions',
                          '${(_data?['positions'] as List?)?.length ?? 0}',
                          const Color(0xFFb0bec5)),
                    ]),
                    const SizedBox(height: 28),

                    // Holdings header + sort filter
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('HOLDINGS', style: TextStyle(
                          color: Color(0xFF90a4ae), fontSize: 12,
                          letterSpacing: 3, fontFamily: 'monospace',
                        )),
                        _sortDropdown(),
                      ],
                    ),
                    const SizedBox(height: 10),

                    // Position cards
                    ..._sortedPositions().map((p) => _positionCard(p)),

                    const SizedBox(height: 16),
                    Text(
                      'Updated ${DateFormat('h:mm a').format(DateTime.now())}',
                      style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 11),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _sortDropdown() {
    const labels = {
      SortMode.value:     'Highest Value',
      SortMode.gainPct:   'Biggest Gain',
      SortMode.symbol:    'A → Z',
      SortMode.assetType: 'Type',
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFF4fc3f7).withOpacity(0.08),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF4fc3f7).withOpacity(0.3)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<SortMode>(
          value: _sort,
          dropdownColor: const Color(0xFF111827),
          style: const TextStyle(color: Color(0xFF4fc3f7), fontSize: 12),
          icon: const Icon(Icons.sort, color: Color(0xFF4fc3f7), size: 14),
          isDense: true,
          items: SortMode.values.map((m) => DropdownMenuItem(
            value: m,
            child: Text(labels[m]!),
          )).toList(),
          onChanged: (m) { if (m != null) setState(() => _sort = m); },
        ),
      ),
    );
  }

  Widget _statCard(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF0d1525),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(color: color.withOpacity(0.7), fontSize: 11)),
          const SizedBox(height: 6),
          Text(value, style: TextStyle(
              color: color, fontSize: 22, fontWeight: FontWeight.bold)),
        ]),
      ),
    );
  }

  Widget _positionCard(Map p) {
    final ret   = (p['return_pct'] as num).toDouble();
    final color = ret >= 0 ? const Color(0xFF00b894) : Colors.redAccent;
    final isCrypto = p['asset_type'] == 'crypto';

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: const Color(0xFF0d1525),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.25)),
        boxShadow: [
          BoxShadow(
            color: color.withOpacity(0.06),
            blurRadius: 8, spreadRadius: 1,
          ),
        ],
      ),
      child: Row(children: [
        // Icon badge
        Container(
          width: 40, height: 40,
          decoration: BoxDecoration(
            color: color.withOpacity(0.12),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Center(
            child: Text(
              (p['symbol'] as String).substring(0, 1),
              style: TextStyle(color: color,
                  fontWeight: FontWeight.bold, fontSize: 16),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Text(p['symbol'], style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: Colors.white10,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(isCrypto ? 'CRYPTO' : 'STOCK',
                    style: const TextStyle(color: Colors.white38, fontSize: 9)),
              ),
            ]),
            const SizedBox(height: 3),
            Text(_usd.format(p['equity']),
                style: const TextStyle(color: Color(0xFFb0bec5), fontSize: 13)),
          ]),
        ),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text('${ret >= 0 ? '+' : ''}${ret.toStringAsFixed(2)}%',
              style: TextStyle(color: color,
                  fontSize: 15, fontWeight: FontWeight.bold)),
          Text('avg \$${(p['avg_cost'] as num?)?.toStringAsFixed(2) ?? '--'}',
              style: const TextStyle(color: Colors.white30, fontSize: 11)),
        ]),
      ]),
    );
  }
}
