import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../services/api_service.dart';
import '../services/local_bills.dart';

class BillsScreen extends StatefulWidget {
  const BillsScreen({super.key});
  @override
  State<BillsScreen> createState() => _BillsScreenState();
}

class _BillsScreenState extends State<BillsScreen> {
  final _fmt = NumberFormat.currency(symbol: '\$');
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  List<Map<String, dynamic>> _allBills = [];
  List<Map<String, dynamic>> _bills = [];
  List<Map<String, dynamic>> _stats = [];
  bool _loading = true;
  bool _showSpending = false;
  String _sortMode = 'default';

  // Pay period strip
  DateTime? _paycheckRef;
  double _paycheckAmount = 0;
  String _paycheckLabel = 'Paycheck';
  bool _payPeriodExpanded = false;

  // Auto-match
  List<Map<String, dynamic>> _txns = [];
  List<_BillMatch> _potentialMatches = [];
  Set<String> _dismissedMatchKeys = {};

  static const _catLabels = {
    'RENT_AND_UTILITIES':        'Rent & Utilities',
    'FOOD_AND_DRINK':            'Food & Drink',
    'GENERAL_MERCHANDISE':       'Shopping',
    'TRAVEL':                    'Travel',
    'ENTERTAINMENT':             'Entertainment',
    'HEALTHCARE':                'Healthcare',
    'TRANSFER_OUT':              'Transfer Out',
    'LOAN_PAYMENTS':             'Loan Payments',
    'PERSONAL_CARE':             'Personal Care',
    'GENERAL_SERVICES':          'Services',
    'INCOME':                    'Income',
    'GOVERNMENT_AND_NON_PROFIT': 'Government',
  };

  static String _label(String? raw) =>
      _catLabels[raw] ?? (raw ?? 'Other').replaceAll('_', ' ').toLowerCase()
          .split(' ').map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1)).join(' ');

  // ── paycheck helpers ─────────────────────────────────────────────────────

  DateTime? get _nextPayday {
    if (_paycheckRef == null) return null;
    var d = DateTime(_paycheckRef!.year, _paycheckRef!.month, _paycheckRef!.day);
    final now = DateTime.now();
    while (!d.isAfter(now)) {
      d = d.add(const Duration(days: 14));
    }
    return d;
  }

  DateTime? get _currentPeriodStart {
    if (_paycheckRef == null) return null;
    var d = DateTime(_paycheckRef!.year, _paycheckRef!.month, _paycheckRef!.day);
    final now = DateTime.now();
    while (d.add(const Duration(days: 14)).isBefore(now)) d = d.add(const Duration(days: 14));
    return d;
  }

  DateTime? get _currentPeriodEnd => _currentPeriodStart?.add(const Duration(days: 13));

  List<Map<String, dynamic>> get _billsDuePeriod {
    final start = _currentPeriodStart;
    final end = _currentPeriodEnd;
    if (start == null || end == null) return [];
    return _allBills.where((b) {
      final day = b['due_day'];
      if (day == null) return false;
      final due = DateTime(start.year, start.month, day);
      return !due.isBefore(start) && !due.isAfter(end);
    }).toList();
  }

  // ── init & load ───────────────────────────────────────────────────────────

  @override
  void initState() {
    super.initState();
    _loadDismissed().then((_) => _load());
  }

  Future<void> _loadDismissed() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString('dismissed_bill_matches');
    if (raw != null) {
      _dismissedMatchKeys = Set<String>.from(jsonDecode(raw));
    }
  }

  Future<void> _load() async {
    setState(() => _loading = true);

    // Load paycheck prefs
    final p = await SharedPreferences.getInstance();
    final refMs = p.getInt('paycheck_ref_date_ms');
    final amount = p.getDouble('paycheck_amount') ?? 0;
    final label = p.getString('paycheck_label') ?? 'Paycheck';

    // Load local bills; migrate from backend if first run
    var allLocal = await LocalBills.load();
    if (allLocal.isEmpty) {
      try {
        final backend = await ApiService.getBills(_month.month, _month.year);
        await LocalBills.migrateIfNeeded(backend, _month.month, _month.year);
        allLocal = await LocalBills.load();
      } catch (_) {}
    }

    List<Map<String, dynamic>> stats = _stats;
    List<Map<String, dynamic>> txns = [];

    await Future.wait([
      ApiService.getStats(_month.month, _month.year).then((raw) {
        stats = raw.where((s) {
          final v = double.tryParse(s['category_total']?.toString() ?? '0') ?? 0;
          return v > 0 && s['category'] != null;
        }).toList();
      }).catchError((_) {}),
      ApiService.getTransactions(_month.month, _month.year).then((t) {
        txns = t;
      }).catchError((_) {}),
    ]);

    if (mounted) {
      setState(() {
        _paycheckRef = refMs != null ? DateTime.fromMillisecondsSinceEpoch(refMs) : null;
        _paycheckAmount = amount;
        _paycheckLabel = label;
        _allBills = allLocal;
        _bills = LocalBills.forMonth(allLocal, _month.month, _month.year);
        _stats = stats;
        _txns = txns;
        _loading = false;
      });
      _detectMatches();
    }
  }

  void _detectMatches() {
    final matches = <_BillMatch>[];
    for (final bill in _bills) {
      if (bill['paid'] == true) continue;
      final billId = bill['id']?.toString() ?? '';
      final billName = (bill['name'] ?? '').toString().toLowerCase();
      final billAmt = double.tryParse(bill['amount']?.toString() ?? '0') ?? 0;

      for (final txn in _txns) {
        final txnCat = (txn['category'] ?? '').toString().toUpperCase();
        if (txnCat.contains('INCOME') || txnCat.contains('TRANSFER')) continue;

        final txnId = txn['transaction_id']?.toString() ?? txn['id']?.toString() ?? '';
        final matchKey = '$billId:$txnId';
        if (_dismissedMatchKeys.contains(matchKey)) continue;

        final txnMerchant = (txn['merchant_name'] ?? '').toString().toLowerCase();
        final txnName = (txn['name'] ?? '').toString().toLowerCase();
        final txnAmt = (txn['amount'] as num?)?.toDouble() ?? 0.0;

        final billWords = billName.split(RegExp(r'\s+')).where((w) => w.length >= 4).toList();
        final nameMatch = billWords.any((w) => txnMerchant.contains(w) || txnName.contains(w));
        if (!nameMatch) continue;

        if (billAmt > 0) {
          final diff = (txnAmt - billAmt).abs();
          if (diff / billAmt > 0.20) continue;
        }

        matches.add(_BillMatch(bill, txn));
        break;
      }
    }
    setState(() => _potentialMatches = matches);
  }

  Future<void> _dismissMatch(String key) async {
    _dismissedMatchKeys.add(key);
    final p = await SharedPreferences.getInstance();
    await p.setString('dismissed_bill_matches', jsonEncode(_dismissedMatchKeys.toList()));
    setState(() => _potentialMatches.removeWhere((m) {
      final billId = m.bill['id']?.toString() ?? '';
      final txnId = m.txn['transaction_id']?.toString() ?? m.txn['id']?.toString() ?? '';
      return '$billId:$txnId' == key;
    }));
  }

  // ── CRUD ─────────────────────────────────────────────────────────────────

  Future<void> _togglePaid(Map<String, dynamic> bill) async {
    final paid = !(bill['paid'] == true);
    final id = bill['id'].toString();
    final updated = await LocalBills.setPaid(id, _month.month, _month.year, paid);
    // fire-and-forget to backend
    ApiService.setBillPaid(bill['id'], _month.month, _month.year, paid).catchError((_) {});
    if (mounted) {
      setState(() {
        _allBills = updated;
        _bills = LocalBills.forMonth(updated, _month.month, _month.year);
      });
      _detectMatches();
    }
  }

  Future<void> _deleteBill(String id) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: PC.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Delete Bill', style: TextStyle(color: Colors.white)),
        content: const Text('Remove this bill permanently?',
            style: TextStyle(color: PC.sage)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel', style: TextStyle(color: PC.sage))),
          TextButton(onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete', style: TextStyle(color: Colors.redAccent))),
        ],
      ),
    );
    if (ok == true) {
      final updated = await LocalBills.delete(id);
      // fire-and-forget
      if (id.startsWith('lb_')) {
        ApiService.deleteBill(int.tryParse(id.replaceFirst('lb_', '')) ?? 0)
            .catchError((_) {});
      }
      if (mounted) {
        setState(() {
          _allBills = updated;
          _bills = LocalBills.forMonth(updated, _month.month, _month.year);
        });
      }
    }
  }

  // ── build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final totalDue  = _bills.fold<double>(0, (s, b) =>
        s + (double.tryParse(b['amount']?.toString() ?? '0') ?? 0));
    final totalPaid = _bills.where((b) => b['paid'] == true).fold<double>(0, (s, b) =>
        s + (double.tryParse(b['amount']?.toString() ?? '0') ?? 0));

    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(
        title: const Text('BILLS'),
        actions: [
          PopupMenuButton<String>(
            icon: Icon(
              _sortMode == 'category' ? Icons.category_outlined
                : _sortMode == 'due'  ? Icons.calendar_today_outlined
                : _sortMode == 'amount' ? Icons.attach_money
                : Icons.sort,
              color: _sortMode == 'default' ? PC.sage : PC.pink,
            ),
            color: PC.card,
            onSelected: (v) => setState(() => _sortMode = v),
            itemBuilder: (_) => [
              _sortItem('default',  Icons.sort,                    'Default'),
              _sortItem('category', Icons.category_outlined,       'By Category'),
              _sortItem('due',      Icons.calendar_today_outlined,  'By Due Date'),
              _sortItem('amount',   Icons.attach_money,            'By Amount'),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.auto_awesome),
            color: PC.gold,
            tooltip: 'Find Recurring',
            onPressed: _showRecurring,
          ),
          IconButton(
            icon: const Icon(Icons.add),
            color: PC.pink,
            onPressed: () => _showBillSheet(null),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: PC.pink))
          : Column(children: [
              // ── Pay period strip ──────────────────────────────────────────
              _buildPayPeriodStrip(),

              // ── Month picker ──────────────────────────────────────────────
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  IconButton(
                    icon: const Icon(Icons.chevron_left, color: PC.sage),
                    onPressed: () {
                      setState(() => _month = DateTime(_month.year, _month.month - 1));
                      _load();
                    },
                  ),
                  Text(DateFormat('MMMM yyyy').format(_month),
                      style: const TextStyle(color: Colors.white, fontSize: 16,
                          fontWeight: FontWeight.bold)),
                  IconButton(
                    icon: const Icon(Icons.chevron_right, color: PC.sage),
                    onPressed: _month.month == DateTime.now().month &&
                            _month.year == DateTime.now().year ? null : () {
                      setState(() => _month = DateTime(_month.year, _month.month + 1));
                      _load();
                    },
                  ),
                ]),
              ),

              // ── Summary bar ───────────────────────────────────────────────
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                  decoration: BoxDecoration(
                    color: PC.card,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: PC.pink.withOpacity(0.2)),
                  ),
                  child: Row(children: [
                    Expanded(child: Column(children: [
                      const Text('TOTAL DUE', style: TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 2)),
                      const SizedBox(height: 4),
                      Text(_fmt.format(totalDue),
                          style: const TextStyle(color: PC.gold, fontSize: 18, fontWeight: FontWeight.bold)),
                    ])),
                    Container(width: 1, height: 40, color: Colors.white10),
                    Expanded(child: Column(children: [
                      const Text('PAID', style: TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 2)),
                      const SizedBox(height: 4),
                      Text(_fmt.format(totalPaid),
                          style: const TextStyle(color: PC.green, fontSize: 18, fontWeight: FontWeight.bold)),
                    ])),
                    Container(width: 1, height: 40, color: Colors.white10),
                    Expanded(child: Column(children: [
                      const Text('REMAINING', style: TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 2)),
                      const SizedBox(height: 4),
                      Text(_fmt.format(totalDue - totalPaid),
                          style: const TextStyle(color: PC.red, fontSize: 18, fontWeight: FontWeight.bold)),
                    ])),
                  ]),
                ),
              ),

              // ── Auto-match banner ─────────────────────────────────────────
              if (_potentialMatches.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: GestureDetector(
                    onTap: _showMatchReview,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: PC.green.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: PC.green.withOpacity(0.35)),
                      ),
                      child: Row(children: [
                        const Icon(Icons.auto_awesome, color: PC.green, size: 16),
                        const SizedBox(width: 8),
                        Expanded(child: Text(
                          '${_potentialMatches.length} bill${_potentialMatches.length > 1 ? 's' : ''} may have been paid — tap to review',
                          style: const TextStyle(color: PC.green, fontSize: 12),
                        )),
                        const Icon(Icons.chevron_right, color: PC.green, size: 18),
                      ]),
                    ),
                  ),
                ),

              // ── Spending categories ───────────────────────────────────────
              if (_stats.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: GestureDetector(
                    onTap: () => setState(() => _showSpending = !_showSpending),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: PC.card,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: PC.gold.withOpacity(0.3)),
                      ),
                      child: Row(children: [
                        const Icon(Icons.bar_chart, color: PC.gold, size: 16),
                        const SizedBox(width: 8),
                        const Expanded(child: Text('ADD FROM SPENDING',
                            style: TextStyle(color: PC.gold, fontSize: 11,
                                letterSpacing: 2, fontWeight: FontWeight.bold))),
                        Icon(_showSpending ? Icons.expand_less : Icons.expand_more,
                            color: PC.gold, size: 18),
                      ]),
                    ),
                  ),
                ),
              if (_showSpending)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: Container(
                    decoration: BoxDecoration(
                      color: PC.card,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.white.withOpacity(0.06)),
                    ),
                    child: Column(
                      children: _stats.map((s) {
                        final cat    = s['category']?.toString();
                        final lbl    = _label(cat);
                        final amt    = double.tryParse(s['category_total']?.toString() ?? '0') ?? 0;
                        final tracked = _bills.any((b) {
                          final bName = (b['name'] ?? '').toString().toLowerCase();
                          return bName.contains(lbl.toLowerCase()) ||
                              lbl.toLowerCase().contains(bName) ||
                              (b['category'] ?? '').toString().toLowerCase() == lbl.toLowerCase();
                        });
                        return ListTile(
                          dense: true,
                          title: Text(lbl,
                              style: TextStyle(
                                  color: tracked ? PC.sage : Colors.white,
                                  fontSize: 13,
                                  decoration: tracked ? TextDecoration.lineThrough : null,
                                  decorationColor: PC.sage)),
                          subtitle: tracked
                              ? const Text('Already tracked as a bill',
                                  style: TextStyle(color: PC.sage, fontSize: 10))
                              : null,
                          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                            Text(_fmt.format(amt),
                                style: TextStyle(
                                    color: tracked ? PC.sage : PC.gold,
                                    fontWeight: FontWeight.bold, fontSize: 13)),
                            const SizedBox(width: 8),
                            tracked
                                ? const Icon(Icons.check_circle, color: PC.green, size: 20)
                                : ElevatedButton(
                                    style: ElevatedButton.styleFrom(
                                        backgroundColor: PC.pink,
                                        foregroundColor: PC.background,
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                        minimumSize: Size.zero,
                                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                        shape: RoundedRectangleBorder(
                                            borderRadius: BorderRadius.circular(6))),
                                    onPressed: () => _showBillSheet(null,
                                        prefillName: lbl, prefillAmount: amt),
                                    child: const Text('ADD',
                                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                                  ),
                          ]),
                        );
                      }).toList(),
                    ),
                  ),
                ),

              // ── Bill list ─────────────────────────────────────────────────
              Expanded(child: _bills.isEmpty
                  ? _empty()
                  : RefreshIndicator(
                      color: PC.pink,
                      backgroundColor: PC.surface,
                      onRefresh: _load,
                      child: _sortMode == 'category'
                          ? _groupedList()
                          : ListView.builder(
                              padding: const EdgeInsets.fromLTRB(16, 0, 16, 40),
                              itemCount: _sortedBills.length,
                              itemBuilder: (_, i) => _billCard(_sortedBills[i]),
                            ),
                    )),
            ]),
    );
  }

  // ── Pay period strip widget ───────────────────────────────────────────────

  Widget _buildPayPeriodStrip() {
    if (_paycheckRef == null) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: PC.card,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: PC.sage.withOpacity(0.2)),
          ),
          child: Row(children: [
            const Icon(Icons.payments_outlined, color: PC.gold, size: 16),
            const SizedBox(width: 8),
            const Expanded(child: Text(
              'Set up paycheck — tap Paycheck in the More menu',
              style: TextStyle(color: PC.sage, fontSize: 12),
            )),
          ]),
        ),
      );
    }

    final nextPay = _nextPayday!;
    final start = _currentPeriodStart!;
    final end = _currentPeriodEnd!;
    final periodBills = _billsDuePeriod;
    final periodTotal = periodBills.fold<double>(0,
        (s, b) => s + (double.tryParse(b['amount']?.toString() ?? '0') ?? 0));
    final dateFmt = DateFormat('MMM d');
    final daysAway = nextPay.difference(DateTime.now()).inDays;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: GestureDetector(
        onTap: () => setState(() => _payPeriodExpanded = !_payPeriodExpanded),
        child: Container(
          decoration: BoxDecoration(
            color: PC.card,
            borderRadius: BorderRadius.circular(12),
            border: Border(
              left: const BorderSide(color: PC.green, width: 3),
              top: BorderSide(color: Colors.white.withOpacity(0.06)),
              right: BorderSide(color: Colors.white.withOpacity(0.06)),
              bottom: BorderSide(color: Colors.white.withOpacity(0.06)),
            ),
          ),
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(children: [
                const Icon(Icons.payments_outlined, color: PC.green, size: 16),
                const SizedBox(width: 8),
                Text('Next payday: ${dateFmt.format(nextPay)}',
                    style: const TextStyle(color: Colors.white, fontSize: 13,
                        fontWeight: FontWeight.w600)),
                const SizedBox(width: 6),
                Text('(${daysAway}d away)',
                    style: const TextStyle(color: PC.sage, fontSize: 11)),
                const Spacer(),
                Text(_fmt.format(_paycheckAmount),
                    style: const TextStyle(color: PC.green, fontSize: 13,
                        fontWeight: FontWeight.bold)),
                const SizedBox(width: 4),
                Icon(_payPeriodExpanded ? Icons.expand_less : Icons.expand_more,
                    color: PC.sage, size: 18),
              ]),
            ),
            if (_payPeriodExpanded) ...[
              const Divider(color: Colors.white10, height: 1),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                child: Row(children: [
                  Text(
                    'Period: ${dateFmt.format(start)} – ${dateFmt.format(end)}',
                    style: const TextStyle(color: PC.sage, fontSize: 12),
                  ),
                  const Spacer(),
                  Text(
                    '${periodBills.length} bill${periodBills.length != 1 ? 's' : ''} · ${_fmt.format(periodTotal)}',
                    style: const TextStyle(color: PC.gold, fontSize: 12,
                        fontWeight: FontWeight.bold),
                  ),
                ]),
              ),
            ],
          ]),
        ),
      ),
    );
  }

  // ── helpers ───────────────────────────────────────────────────────────────

  PopupMenuItem<String> _sortItem(String value, IconData icon, String label) =>
      PopupMenuItem(
        value: value,
        child: Row(children: [
          Icon(icon, size: 16, color: _sortMode == value ? PC.pink : PC.sage),
          const SizedBox(width: 10),
          Text(label, style: TextStyle(
              color: _sortMode == value ? PC.pink : Colors.white,
              fontSize: 13,
              fontWeight: _sortMode == value ? FontWeight.bold : FontWeight.normal)),
        ]),
      );

  List<Map<String, dynamic>> get _sortedBills {
    final sorted = List<Map<String, dynamic>>.from(_bills);
    if (_sortMode == 'due') {
      sorted.sort((a, b) => (a['due_day'] ?? 99).compareTo(b['due_day'] ?? 99));
    } else if (_sortMode == 'amount') {
      sorted.sort((a, b) {
        final av = double.tryParse(a['amount']?.toString() ?? '0') ?? 0;
        final bv = double.tryParse(b['amount']?.toString() ?? '0') ?? 0;
        return bv.compareTo(av);
      });
    }
    return sorted;
  }

  Widget _groupedList() {
    final Map<String, List<Map<String, dynamic>>> groups = {};
    for (final b in _bills) {
      final cat = (b['category'] ?? 'Other').toString();
      groups.putIfAbsent(cat, () => []).add(b);
    }
    final sortedKeys = groups.keys.toList()..sort();

    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 40),
      itemCount: sortedKeys.fold<int>(0, (s, k) => s + 1 + groups[k]!.length),
      itemBuilder: (_, i) {
        int cursor = 0;
        for (final cat in sortedKeys) {
          if (i == cursor) {
            final catBills = groups[cat]!;
            final subtotal = catBills.fold<double>(0,
                (s, b) => s + (double.tryParse(b['amount']?.toString() ?? '0') ?? 0));
            final unpaid = catBills.where((b) => b['paid'] != true).length;
            return Padding(
              padding: const EdgeInsets.only(top: 12, bottom: 6),
              child: Row(children: [
                _badge(cat),
                const SizedBox(width: 8),
                Text('$unpaid unpaid', style: const TextStyle(color: PC.sage, fontSize: 11)),
                const Spacer(),
                Text(_fmt.format(subtotal),
                    style: const TextStyle(color: PC.gold, fontSize: 12,
                        fontWeight: FontWeight.bold)),
              ]),
            );
          }
          cursor++;
          final billIdx = i - cursor;
          if (billIdx < groups[cat]!.length) {
            return _billCard(groups[cat]![billIdx]);
          }
          cursor += groups[cat]!.length;
        }
        return const SizedBox();
      },
    );
  }

  Widget _billCard(Map<String, dynamic> b) {
    final paid    = b['paid'] == true;
    final amt     = double.tryParse(b['amount']?.toString() ?? '0') ?? 0;
    final dueDay  = b['due_day'];
    final cat     = b['category'] ?? 'Bill';
    final now     = DateTime.now();
    final isOverdue = !paid && dueDay != null &&
        DateTime(now.year, now.month, dueDay).isBefore(now) &&
        _month.month == now.month && _month.year == now.year;

    return Dismissible(
      key: Key(b['id'].toString()),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        decoration: BoxDecoration(
          color: Colors.red.withOpacity(0.3),
          borderRadius: BorderRadius.circular(14),
        ),
        child: const Icon(Icons.delete_outline, color: Colors.redAccent),
      ),
      confirmDismiss: (_) async {
        await _deleteBill(b['id'].toString());
        return false;
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(
          color: PC.card,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: isOverdue
              ? PC.red.withOpacity(0.4)
              : Colors.white.withOpacity(0.06)),
        ),
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          leading: GestureDetector(
            onTap: () => _togglePaid(b),
            child: Container(
              width: 36, height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: paid ? PC.green.withOpacity(0.15) : PC.card,
                border: Border.all(
                    color: paid ? PC.green : (isOverdue ? PC.red : PC.grove), width: 2),
              ),
              child: paid
                  ? const Icon(Icons.check, color: PC.green, size: 18)
                  : isOverdue
                      ? const Icon(Icons.warning_amber, color: PC.red, size: 16)
                      : null,
            ),
          ),
          title: Text(b['name'] ?? '',
              style: TextStyle(
                  color: paid ? PC.sage : Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  decoration: paid ? TextDecoration.lineThrough : null,
                  decorationColor: PC.sage)),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Row(children: [
              _badge(cat),
              const SizedBox(width: 8),
              if (dueDay != null)
                Text('Due $dueDay${_ordinal(dueDay)}',
                    style: TextStyle(color: isOverdue ? PC.red : PC.sage, fontSize: 11)),
              if (paid && b['paid_date'] != null) ...[
                const SizedBox(width: 8),
                Text('Paid ${b['paid_date']}',
                    style: const TextStyle(color: PC.green, fontSize: 11)),
              ],
            ]),
          ),
          trailing: Text(_fmt.format(amt),
              style: TextStyle(
                  color: paid ? PC.sage : PC.gold,
                  fontSize: 15, fontWeight: FontWeight.bold)),
          onTap: () => _showBillSheet(b),
        ),
      ),
    );
  }

  String _ordinal(int day) {
    if (day >= 11 && day <= 13) return 'th';
    switch (day % 10) {
      case 1: return 'st';
      case 2: return 'nd';
      case 3: return 'rd';
      default: return 'th';
    }
  }

  Widget _badge(String label) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    decoration: BoxDecoration(
      color: PC.pink.withOpacity(0.12),
      borderRadius: BorderRadius.circular(4),
      border: Border.all(color: PC.pink.withOpacity(0.3)),
    ),
    child: Text(label.toUpperCase(),
        style: const TextStyle(color: PC.pink, fontSize: 9, letterSpacing: 1)),
  );

  Widget _empty() => Center(child: Column(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      Icon(Icons.receipt_long, size: 64, color: PC.pink.withOpacity(0.3)),
      const SizedBox(height: 16),
      const Text('No bills yet', style: TextStyle(color: PC.sage, fontSize: 16)),
      const SizedBox(height: 8),
      const Text('Tap + to add a bill', style: TextStyle(color: PC.sage, fontSize: 13)),
    ],
  ));

  // ── Match review sheet ────────────────────────────────────────────────────

  void _showMatchReview() {
    showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(builder: (ctx, set) {
        final matches = List<_BillMatch>.from(_potentialMatches);
        if (matches.isEmpty) {
          Navigator.pop(ctx);
          return const SizedBox();
        }
        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.6,
          maxChildSize: 0.9,
          builder: (_, ctrl) => SafeArea(top: false, child: Column(children: [
            const SizedBox(height: 8),
            Container(width: 40, height: 4,
                decoration: BoxDecoration(color: Colors.white24,
                    borderRadius: BorderRadius.circular(2))),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
              child: Row(children: [
                const Icon(Icons.auto_awesome, color: PC.gold, size: 18),
                const SizedBox(width: 8),
                const Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Possible Bill Payments',
                        style: TextStyle(color: Colors.white, fontSize: 16,
                            fontWeight: FontWeight.bold)),
                    Text('Transactions that look like bill payments.',
                        style: TextStyle(color: PC.sage, fontSize: 11)),
                  ],
                )),
                IconButton(
                  icon: const Icon(Icons.close, color: PC.sage),
                  onPressed: () => Navigator.pop(ctx),
                ),
              ]),
            ),
            const Divider(color: Colors.white10, height: 1),
            Expanded(child: ListView.builder(
              controller: ctrl,
              padding: const EdgeInsets.all(16),
              itemCount: matches.length,
              itemBuilder: (_, i) {
                final m = matches[i];
                final billAmt = double.tryParse(m.bill['amount']?.toString() ?? '0') ?? 0;
                final txnAmt = (m.txn['amount'] as num?)?.toDouble() ?? 0.0;
                final billId = m.bill['id']?.toString() ?? '';
                final txnId = m.txn['transaction_id']?.toString() ?? m.txn['id']?.toString() ?? '';
                final matchKey = '$billId:$txnId';
                final amtDiffers = (txnAmt - billAmt).abs() > 0.01;

                return Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: PC.card,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: PC.gold.withOpacity(0.3)),
                  ),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      const Icon(Icons.receipt_long, color: PC.pink, size: 16),
                      const SizedBox(width: 6),
                      Expanded(child: Text(m.bill['name'] ?? '',
                          style: const TextStyle(color: Colors.white,
                              fontSize: 14, fontWeight: FontWeight.bold))),
                      Text(_fmt.format(billAmt),
                          style: const TextStyle(color: PC.gold, fontWeight: FontWeight.bold)),
                    ]),
                    const SizedBox(height: 6),
                    Row(children: [
                      const Icon(Icons.arrow_forward, color: PC.sage, size: 14),
                      const SizedBox(width: 6),
                      Expanded(child: Text(
                          m.txn['merchant_name'] ?? m.txn['name'] ?? '',
                          style: const TextStyle(color: PC.sage, fontSize: 12),
                          overflow: TextOverflow.ellipsis)),
                      Text(_fmt.format(txnAmt),
                          style: TextStyle(
                              color: amtDiffers ? PC.gold : PC.sage,
                              fontSize: 12)),
                    ]),
                    if (amtDiffers)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text('Amount differs from bill — confirm before marking paid.',
                            style: TextStyle(color: PC.gold.withOpacity(0.8), fontSize: 10)),
                      ),
                    const SizedBox(height: 10),
                    Row(children: [
                      Expanded(child: OutlinedButton(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: PC.sage,
                          side: const BorderSide(color: PC.grove),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        onPressed: () async {
                          await _dismissMatch(matchKey);
                          set(() => matches.removeAt(i));
                          if (matches.isEmpty && ctx.mounted) Navigator.pop(ctx);
                        },
                        child: const Text('Skip', style: TextStyle(fontSize: 12)),
                      )),
                      const SizedBox(width: 10),
                      Expanded(child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: PC.green,
                          foregroundColor: Colors.black,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        onPressed: () async {
                          await _dismissMatch(matchKey);
                          set(() => matches.removeAt(i));
                          await _togglePaid(m.bill);
                          if (matches.isEmpty && ctx.mounted) Navigator.pop(ctx);
                        },
                        child: const Text('Mark Paid',
                            style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      )),
                    ]),
                  ]),
                );
              },
            )),
          ])),
        );
      }),
    );
  }

  // ── Recurring sheet ───────────────────────────────────────────────────────

  Future<void> _showRecurring() async {
    List<Map<String, dynamic>> results = [];
    bool loading = true;

    await showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(builder: (ctx, set) {
        if (loading) {
          ApiService.getRecurring().then((r) {
            set(() { results = r; loading = false; });
          }).catchError((_) {
            set(() => loading = false);
          });
        }
        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.6,
          maxChildSize: 0.9,
          builder: (_, ctrl) => SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  const Icon(Icons.auto_awesome, color: PC.gold, size: 18),
                  const SizedBox(width: 8),
                  const Text('Recurring Payments',
                      style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close, color: PC.sage),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ]),
                const Text('Merchants appearing in 2+ months. Tap to add as a bill.',
                    style: TextStyle(color: PC.sage, fontSize: 12)),
                const SizedBox(height: 16),
                loading
                    ? const Center(child: Padding(
                        padding: EdgeInsets.all(32),
                        child: CircularProgressIndicator(color: PC.pink)))
                    : results.isEmpty
                        ? const Center(child: Padding(
                            padding: EdgeInsets.all(32),
                            child: Text('No recurring payments found yet.\nSync more transactions first.',
                                textAlign: TextAlign.center,
                                style: TextStyle(color: PC.sage, fontSize: 13))))
                        : Expanded(child: ListView.builder(
                            controller: ctrl,
                            itemCount: results.length,
                            itemBuilder: (_, i) {
                              final r = results[i];
                              final amt = double.tryParse(r['typical_amount']?.toString() ?? '0') ?? 0;
                              final months = r['month_count']?.toString() ?? '?';
                              final day = int.tryParse(r['typical_day']?.toString() ?? '');
                              return ListTile(
                                contentPadding: EdgeInsets.zero,
                                title: Text(r['merchant'] ?? '',
                                    style: const TextStyle(color: Colors.white, fontSize: 14),
                                    overflow: TextOverflow.ellipsis),
                                subtitle: Text('$months months · Due ~day ${day ?? '?'}',
                                    style: const TextStyle(color: PC.sage, fontSize: 11)),
                                trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                                  Text(_fmt.format(amt),
                                      style: const TextStyle(color: PC.gold, fontWeight: FontWeight.bold)),
                                  const SizedBox(width: 8),
                                  ElevatedButton(
                                    style: ElevatedButton.styleFrom(
                                        backgroundColor: PC.pink, foregroundColor: PC.background,
                                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                        minimumSize: Size.zero,
                                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
                                    onPressed: () async {
                                      Navigator.pop(ctx);
                                      final fields = {
                                        'name': r['merchant'] ?? '',
                                        'amount': amt,
                                        'due_day': day,
                                        'category': 'Subscription',
                                      };
                                      final updated = await LocalBills.create(fields);
                                      ApiService.createBill(
                                        name: r['merchant'] ?? '',
                                        amount: amt,
                                        dueDay: day,
                                        category: 'Subscription',
                                      ).catchError((_) {});
                                      if (mounted) {
                                        setState(() {
                                          _allBills = updated;
                                          _bills = LocalBills.forMonth(updated, _month.month, _month.year);
                                        });
                                      }
                                    },
                                    child: const Text('ADD',
                                        style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                                  ),
                                ]),
                              );
                            },
                          )),
              ]),
            ),
          ),
        );
      }),
    );
  }

  // ── Add/Edit bill sheet ───────────────────────────────────────────────────

  void _showBillSheet(Map<String, dynamic>? bill,
      {String? prefillName, double? prefillAmount}) {
    final nameCtrl = TextEditingController(
        text: bill?['name'] ?? prefillName ?? '');
    final amtCtrl  = TextEditingController(
        text: bill != null
            ? (double.tryParse(bill['amount']?.toString() ?? '0') ?? 0).toStringAsFixed(2)
            : prefillAmount != null ? prefillAmount.toStringAsFixed(2) : '');
    final dueCtrl  = TextEditingController(
        text: bill?['due_day']?.toString() ?? '');
    String cat = bill?['category'] ?? 'Bill';
    final cats = ['Bill', 'Subscription', 'Insurance', 'Utilities', 'Rent', 'Loan', 'Other'];

    showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => SafeArea(
        top: false,
        child: Padding(
          padding: EdgeInsets.only(
              left: 20, right: 20, top: 20,
              bottom: MediaQuery.of(ctx).viewInsets.bottom + 16),
          child: StatefulBuilder(builder: (ctx, set) => Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(bill == null ? 'Add Bill' : 'Edit Bill',
                  style: const TextStyle(color: Colors.white, fontSize: 18,
                      fontWeight: FontWeight.bold)),
              const SizedBox(height: 20),
              _sheetField(nameCtrl, 'Name', TextInputType.text),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: _sheetField(amtCtrl, 'Amount',
                    const TextInputType.numberWithOptions(decimal: true))),
                const SizedBox(width: 12),
                Expanded(child: _sheetField(dueCtrl, 'Due day (1-31)',
                    TextInputType.number)),
              ]),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: cat,
                dropdownColor: PC.card,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: 'Category',
                  labelStyle: const TextStyle(color: PC.sage),
                  filled: true, fillColor: PC.card,
                  border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none),
                ),
                items: cats.map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
                onChanged: (v) => set(() => cat = v ?? cat),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity, height: 48,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                      backgroundColor: PC.pink, foregroundColor: PC.background,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
                  onPressed: () async {
                    final name = nameCtrl.text.trim();
                    final amt  = double.tryParse(amtCtrl.text) ?? 0;
                    final due  = int.tryParse(dueCtrl.text);
                    if (name.isEmpty) return;
                    Navigator.pop(ctx);
                    List<Map<String, dynamic>> updated;
                    if (bill == null) {
                      updated = await LocalBills.create({
                        'name': name, 'amount': amt,
                        'due_day': due, 'category': cat,
                      });
                      ApiService.createBill(
                          name: name, amount: amt, dueDay: due, category: cat)
                          .catchError((_) {});
                    } else {
                      updated = await LocalBills.update(bill['id'].toString(), {
                        'name': name, 'amount': amt,
                        'due_day': due, 'category': cat,
                      });
                      ApiService.updateBill(bill['id'], {
                        'name': name, 'amount': amt,
                        'due_day': due, 'category': cat,
                      }).catchError((_) {});
                    }
                    if (mounted) {
                      setState(() {
                        _allBills = updated;
                        _bills = LocalBills.forMonth(updated, _month.month, _month.year);
                      });
                    }
                  },
                  child: Text(bill == null ? 'ADD BILL' : 'SAVE CHANGES',
                      style: const TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2)),
                ),
              ),
            ],
          )),
        ),
      ),
    );
  }

  Widget _sheetField(TextEditingController ctrl, String label, TextInputType type) =>
      TextField(
        controller: ctrl,
        keyboardType: type,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: const TextStyle(color: PC.sage),
          filled: true, fillColor: PC.card,
          border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
          focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: PC.pink)),
        ),
      );
}

class _BillMatch {
  final Map<String, dynamic> bill;
  final Map<String, dynamic> txn;
  const _BillMatch(this.bill, this.txn);
}
