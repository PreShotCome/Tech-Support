import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ControlsScreen extends StatefulWidget {
  const ControlsScreen({super.key});
  @override
  State<ControlsScreen> createState() => _ControlsScreenState();
}

class _ControlsScreenState extends State<ControlsScreen> {
  bool _paused = false;
  bool _loading = true;
  List<dynamic> _positions = [];
  List<String> _never = [];
  List<dynamic> _queued = [];
  final _buyTicker   = TextEditingController();
  final _buyAmount   = TextEditingController();
  final _neverCtrl   = TextEditingController();
  final _queueTicker = TextEditingController();
  final _queueAmount = TextEditingController();
  String _buyType    = 'stock';
  String _queueType  = 'stock';
  String _queueAction = 'BUY';

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final p = await ApiService.getPortfolio();
      final n = await ApiService.getNeverList();
      List<dynamic> q = [];
      try { q = await ApiService.getQueue(); } catch (_) {}
      if (mounted) setState(() {
        _paused    = p['bot_paused'] ?? false;
        _positions = p['positions'] ?? [];
        _never     = n;
        _queued    = q;
        _loading   = false;
      });
    } catch (_) { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _addQueue() async {
    final t = _queueTicker.text.trim().toUpperCase();
    final a = double.tryParse(_queueAmount.text.trim());
    if (t.isEmpty || a == null || a <= 0) {
      _snack('Enter a valid ticker and amount.'); return;
    }
    try {
      await ApiService.queueOrder(_queueAction, t, a, _queueType);
      _snack('Queued $_queueAction $t for market open');
      _queueTicker.clear(); _queueAmount.clear();
      final q = await ApiService.getQueue();
      if (mounted) setState(() => _queued = q);
    } catch (e) { _snack('Error: $e'); }
  }

  Future<void> _cancelQueued(String id) async {
    try {
      await ApiService.cancelQueued(id);
      final q = await ApiService.getQueue();
      if (mounted) setState(() => _queued = q);
    } catch (e) { _snack('Error: $e'); }
  }

  Future<void> _togglePause() async {
    final r = await ApiService.togglePause();
    setState(() => _paused = r['paused'] ?? _paused);
    _snack(r['message'] ?? '');
  }

  Future<void> _buy() async {
    final t = _buyTicker.text.trim().toUpperCase();
    final a = double.tryParse(_buyAmount.text.trim());
    if (t.isEmpty || a == null || a <= 0) {
      _snack('Enter a valid ticker and amount.'); return;
    }
    try {
      await ApiService.manualBuy(t, a, _buyType);
      _snack('Buy order placed for \$$a of $t');
      _buyTicker.clear(); _buyAmount.clear();
    } catch (e) { _snack('Error: $e'); }
  }

  Future<void> _sell(Map pos) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1a1f35),
        title: Text('Sell ${pos['symbol']}?', style: const TextStyle(color: Colors.white)),
        content: Text('Sell \$${(pos['equity'] as num).toStringAsFixed(2)} of ${pos['symbol']}?',
            style: const TextStyle(color: Colors.white70)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true),
              child: const Text('SELL', style: TextStyle(color: Colors.redAccent))),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ApiService.manualSell(pos['symbol'], (pos['equity'] as num).toDouble(), pos['asset_type']);
      _snack('Sell order placed for ${pos['symbol']}');
      _load();
    } catch (e) { _snack('Error: $e'); }
  }

  Future<void> _addNever() async {
    final sym = _neverCtrl.text.trim().toUpperCase();
    if (sym.isEmpty) return;
    await ApiService.addNever(sym);
    _neverCtrl.clear();
    final n = await ApiService.getNeverList();
    setState(() => _never = n);
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: const Color(0xFF1a1f35)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0a0e1a),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0a0e1a),
        title: const Text('CONTROLS', style: TextStyle(
          color: Color(0xFF90a4ae), letterSpacing: 3, fontSize: 13)),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF4fc3f7)))
          : ListView(padding: const EdgeInsets.all(20), children: [

              // ── Pause toggle ──────────────────────────────────────────────
              _section('BOT STATUS'),
              GestureDetector(
                onTap: _togglePause,
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: _paused
                        ? Colors.red.withOpacity(0.1)
                        : const Color(0xFF00b894).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: _paused ? Colors.red : const Color(0xFF00b894)),
                  ),
                  child: Row(children: [
                    Icon(_paused ? Icons.play_arrow : Icons.pause,
                        color: _paused ? Colors.red : const Color(0xFF00b894), size: 32),
                    const SizedBox(width: 16),
                    Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(_paused ? 'Bot is PAUSED' : 'Bot is RUNNING',
                          style: TextStyle(
                            color: _paused ? Colors.red : const Color(0xFF00b894),
                            fontWeight: FontWeight.bold, fontSize: 16,
                          )),
                      Text(_paused ? 'Tap to resume trading' : 'Tap to pause trading',
                          style: const TextStyle(color: Colors.white38, fontSize: 12)),
                    ]),
                  ]),
                ),
              ),
              const SizedBox(height: 28),

              // ── Manual Buy ────────────────────────────────────────────────
              _section('MANUAL BUY'),
              _card(Column(children: [
                Row(children: [
                  Expanded(
                    child: _input(_buyTicker, 'Ticker (e.g. AAPL)'),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: _input(_buyAmount, 'Amount (\$)')),
                ]),
                const SizedBox(height: 10),
                Row(children: [
                  _typeChip('stock'), const SizedBox(width: 8), _typeChip('crypto'),
                  const Spacer(),
                  ElevatedButton(
                    onPressed: _buy,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF00b894),
                      foregroundColor: Colors.white,
                    ),
                    child: const Text('BUY'),
                  ),
                ]),
              ])),
              const SizedBox(height: 28),

              // ── Queue for Open ────────────────────────────────────────────
              _section('QUEUE FOR OPEN'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text(
                  'Orders fire at 9:31 AM ET. Reserved cash is held back from the bot.',
                  style: TextStyle(color: Colors.white38, fontSize: 11, height: 1.4),
                ),
                const SizedBox(height: 14),
                Row(children: [
                  _actionChip('BUY'),
                  const SizedBox(width: 8),
                  _actionChip('SELL'),
                ]),
                const SizedBox(height: 10),
                Row(children: [
                  Expanded(child: _input(_queueTicker, 'Ticker (e.g. TSLA)')),
                  const SizedBox(width: 10),
                  Expanded(child: _input(_queueAmount, 'Amount (\$)')),
                ]),
                const SizedBox(height: 10),
                Row(children: [
                  _queueTypeChip('stock'),
                  const SizedBox(width: 8),
                  _queueTypeChip('crypto'),
                  const Spacer(),
                  ElevatedButton(
                    onPressed: _addQueue,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFC9A227),
                      foregroundColor: const Color(0xFF040A22),
                    ),
                    child: const Text('QUEUE'),
                  ),
                ]),
              ])),
              if (_queued.isNotEmpty) ...[
                const SizedBox(height: 10),
                ..._queued.map((q) => Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFC9A227).withOpacity(0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFFC9A227).withOpacity(0.4)),
                  ),
                  child: Row(children: [
                    Text('${q['action']} ${q['ticker']}',
                        style: const TextStyle(
                            color: Color(0xFFC9A227), fontWeight: FontWeight.bold)),
                    const SizedBox(width: 10),
                    Text('\$${(q['amount'] as num).toStringAsFixed(2)}',
                        style: const TextStyle(color: Colors.white70)),
                    const SizedBox(width: 6),
                    Text(q['asset_type'] ?? '',
                        style: const TextStyle(color: Colors.white38, fontSize: 11)),
                    const Spacer(),
                    TextButton(
                      onPressed: () => _cancelQueued(q['id'] as String),
                      child: const Text('CANCEL',
                          style: TextStyle(color: Colors.redAccent)),
                    ),
                  ]),
                )),
              ],
              const SizedBox(height: 28),

              // ── Manual Sell ───────────────────────────────────────────────
              _section('MANUAL SELL'),
              ..._positions.map((p) {
                final ret = (p['return_pct'] as num).toDouble();
                final color = ret >= 0 ? const Color(0xFF00b894) : Colors.redAccent;
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.04),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: Colors.white12),
                  ),
                  child: Row(children: [
                    Text(p['symbol'], style: const TextStyle(
                        color: Colors.white, fontWeight: FontWeight.bold)),
                    const SizedBox(width: 10),
                    Text('\$${(p['equity'] as num).toStringAsFixed(2)}',
                        style: const TextStyle(color: Colors.white54, fontSize: 13)),
                    const SizedBox(width: 6),
                    Text('${ret >= 0 ? '+' : ''}${ret.toStringAsFixed(1)}%',
                        style: TextStyle(color: color, fontSize: 12)),
                    const Spacer(),
                    TextButton(
                      onPressed: () => _sell(p),
                      child: const Text('SELL', style: TextStyle(color: Colors.redAccent)),
                    ),
                  ]),
                );
              }),
              const SizedBox(height: 28),

              // ── Trade Never list ──────────────────────────────────────────
              _section('TRADE NEVER LIST'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: _input(_neverCtrl, 'Add ticker (e.g. GME)')),
                  const SizedBox(width: 10),
                  IconButton(
                    icon: const Icon(Icons.add_circle, color: Color(0xFF4fc3f7)),
                    onPressed: _addNever,
                  ),
                ]),
                const SizedBox(height: 10),
                if (_never.isEmpty)
                  const Text('No symbols blocked.',
                      style: TextStyle(color: Colors.white38, fontSize: 12))
                else
                  Wrap(spacing: 8, runSpacing: 8,
                    children: _never.map((sym) => Chip(
                      label: Text(sym, style: const TextStyle(color: Colors.white)),
                      backgroundColor: Colors.red.withOpacity(0.15),
                      side: const BorderSide(color: Colors.redAccent),
                      deleteIcon: const Icon(Icons.close, size: 16, color: Colors.redAccent),
                      onDeleted: () async {
                        await ApiService.removeNever(sym);
                        final n = await ApiService.getNeverList();
                        setState(() => _never = n);
                      },
                    )).toList(),
                  ),
              ])),
            ]),
    );
  }

  Widget _section(String t) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Text(t, style: const TextStyle(
      color: Color(0xFF90a4ae), fontSize: 11, letterSpacing: 3, fontFamily: 'monospace',
    )),
  );

  Widget _card(Widget child) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: Colors.white.withOpacity(0.04),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: Colors.white12),
    ),
    child: child,
  );

  Widget _input(TextEditingController c, String hint) => TextField(
    controller: c,
    style: const TextStyle(color: Colors.white),
    decoration: InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: Colors.white38),
      filled: true,
      fillColor: Colors.white10,
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8), borderSide: BorderSide.none),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
    ),
  );

  Widget _typeChip(String type) => GestureDetector(
    onTap: () => setState(() => _buyType = type),
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: _buyType == type
            ? const Color(0xFF4fc3f7).withOpacity(0.2)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: _buyType == type
              ? const Color(0xFF4fc3f7)
              : Colors.white24,
        ),
      ),
      child: Text(type, style: TextStyle(
        color: _buyType == type ? const Color(0xFF4fc3f7) : Colors.white38,
        fontSize: 12,
      )),
    ),
  );

  Widget _actionChip(String action) {
    final selected = _queueAction == action;
    final color    = action == 'BUY' ? const Color(0xFF00b894) : Colors.redAccent;
    return GestureDetector(
      onTap: () => setState(() => _queueAction = action),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? color.withOpacity(0.2) : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? color : Colors.white24),
        ),
        child: Text(action, style: TextStyle(
          color: selected ? color : Colors.white38,
          fontWeight: FontWeight.bold,
          fontSize: 12,
        )),
      ),
    );
  }

  Widget _queueTypeChip(String type) => GestureDetector(
    onTap: () => setState(() => _queueType = type),
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: _queueType == type
            ? const Color(0xFF4fc3f7).withOpacity(0.2)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: _queueType == type ? const Color(0xFF4fc3f7) : Colors.white24,
        ),
      ),
      child: Text(type, style: TextStyle(
        color: _queueType == type ? const Color(0xFF4fc3f7) : Colors.white38,
        fontSize: 12,
      )),
    ),
  );
}
