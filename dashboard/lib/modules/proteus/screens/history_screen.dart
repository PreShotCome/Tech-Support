import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});
  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<dynamic> _trades = [];
  bool _loading = true;
  final _usd = NumberFormat.currency(symbol: '\$');

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final t = await ApiService.getTrades();
      if (mounted) setState(() { _trades = t; _loading = false; });
    } catch (_) { if (mounted) setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0a0e1a),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0a0e1a),
        title: const Text('TRADE HISTORY', style: TextStyle(
          color: Color(0xFF90a4ae), letterSpacing: 3, fontSize: 13,
        )),
        actions: [
          IconButton(icon: const Icon(Icons.refresh, color: Color(0xFF4fc3f7)),
              onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF4fc3f7)))
          : _trades.isEmpty
              ? const Center(child: Text('No trades yet.',
                  style: TextStyle(color: Colors.white38)))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _trades.length,
                    itemBuilder: (ctx, i) {
                      final t = _trades[i];
                      final isBuy = t['action'] == 'BUY';
                      final isFailed = (t['source'] ?? '') == 'FAILED';
                      final color = isFailed
                          ? const Color(0xFFFFB300)
                          : (isBuy ? const Color(0xFF00b894) : Colors.redAccent);
                      final ts = DateTime.tryParse(t['ts'] ?? '') ?? DateTime.now();
                      return Container(
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.07),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: color.withOpacity(0.25)),
                        ),
                        child: Row(children: [
                          Container(
                            width: 36, height: 36,
                            decoration: BoxDecoration(
                              color: color.withOpacity(0.15),
                              shape: BoxShape.circle,
                            ),
                            child: Icon(
                                isFailed
                                    ? Icons.error_outline
                                    : (isBuy ? Icons.arrow_upward : Icons.arrow_downward),
                                color: color, size: 18),
                          ),
                          const SizedBox(width: 12),
                          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Row(children: [
                              Text('${t['action']} ${t['ticker']}',
                                  style: TextStyle(color: color,
                                      fontWeight: FontWeight.bold, fontSize: 14)),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.white10,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(t['source'] ?? 'bot',
                                    style: const TextStyle(color: Colors.white38, fontSize: 10)),
                              ),
                            ]),
                            const SizedBox(height: 3),
                            Text(t['note'] ?? '',
                                style: TextStyle(
                                    color: isFailed ? color : Colors.white38,
                                    fontSize: 11),
                                maxLines: isFailed ? 4 : 1,
                                overflow: TextOverflow.ellipsis),
                          ])),
                          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                            Text(_usd.format(t['amount']),
                                style: const TextStyle(color: Colors.white,
                                    fontWeight: FontWeight.bold)),
                            Text(DateFormat('MMM d, h:mm a').format(ts),
                                style: const TextStyle(color: Colors.white38, fontSize: 11)),
                          ]),
                        ]),
                      );
                    },
                  ),
                ),
    );
  }
}
