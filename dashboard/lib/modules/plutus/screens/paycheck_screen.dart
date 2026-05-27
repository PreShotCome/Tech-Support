import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../services/api_service.dart';
import '../services/local_bills.dart';

class PaycheckScreen extends StatefulWidget {
  const PaycheckScreen({super.key});

  @override
  State<PaycheckScreen> createState() => _PaycheckScreenState();
}

class _PaycheckScreenState extends State<PaycheckScreen> {
  final _currFmt = NumberFormat.currency(symbol: '\$');
  final _dateFmt = DateFormat('MMM d');

  // Prefs / config
  DateTime? _refDate;
  double _paycheckAmount = 0;
  String _paycheckLabel = 'Paycheck';

  // Navigation
  int _periodOffset = 0;
  bool _balanceExpanded = false;
  bool _nextPreviewExpanded = false;

  // Data
  List<Map<String, dynamic>> _bills = [];
  List<Map<String, dynamic>> _transactions = [];
  List<Map<String, dynamic>> _recentDeposits = [];
  bool _loadingBills = false;
  bool _loadingTx = false;

  @override
  void initState() {
    super.initState();
    _loadPrefs();
    _loadRecentDeposits();
    requestPaycheckConfig.addListener(_onConfigRequested);
  }

  @override
  void dispose() {
    requestPaycheckConfig.removeListener(_onConfigRequested);
    super.dispose();
  }

  // The Safe-to-Spend screen sets this flag to open the configure sheet here.
  void _onConfigRequested() {
    if (!requestPaycheckConfig.value || !mounted) return;
    requestPaycheckConfig.value = false;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _showConfigureSheet();
    });
  }

  // ── Prefs ──────────────────────────────────────────────────────────────────

  Future<void> _loadPrefs() async {
    final p = await SharedPreferences.getInstance();
    final ms = p.getInt('paycheck_ref_date_ms');
    setState(() {
      _refDate = ms != null ? DateTime.fromMillisecondsSinceEpoch(ms) : null;
      _paycheckAmount = p.getDouble('paycheck_amount') ?? 0;
      _paycheckLabel = p.getString('paycheck_label') ?? 'Paycheck';
    });
    if (_refDate != null) _loadData();
  }

  Future<void> _savePrefs(DateTime refDate, double amount, String label) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt('paycheck_ref_date_ms', refDate.millisecondsSinceEpoch);
    await p.setDouble('paycheck_amount', amount);
    await p.setString('paycheck_label', label);
    setState(() {
      _refDate = refDate;
      _paycheckAmount = amount;
      _paycheckLabel = label;
    });
    _loadData();
    paycheckChanged.value++;
  }

  // Recent income deposits — fuels the "pick a deposit" option in the
  // configure sheet so a real paycheck can be selected with one tap.
  Future<void> _loadRecentDeposits() async {
    try {
      final now = DateTime.now();
      final all = <Map<String, dynamic>>[];
      final seen = <dynamic>{};
      for (int m = 0; m < 3; m++) {
        final d = DateTime(now.year, now.month - m, 1);
        final txns = await ApiService.getTransactions(d.month, d.year);
        for (final t in txns) {
          final amt = double.tryParse(t['amount']?.toString() ?? '0') ?? 0;
          if (amt >= 0) continue; // Plaid stores incoming money as negative
          final id = t['transaction_id'] ?? t['id'] ?? Object();
          if (seen.add(id)) all.add(t);
        }
      }
      all.sort((a, b) => '${b['date']}'.compareTo('${a['date']}'));
      if (mounted) setState(() => _recentDeposits = all);
    } catch (_) {}
  }

  // ── Pay period math ────────────────────────────────────────────────────────

  List<DateTime> _getPayDates() {
    if (_refDate == null) return [];
    DateTime d = _refDate!;
    final cutoff = DateTime.now().subtract(const Duration(days: 180));
    while (d.isAfter(cutoff)) d = d.subtract(const Duration(days: 14));
    d = d.add(const Duration(days: 14));
    final dates = <DateTime>[];
    for (int i = 0; i < 22; i++) {
      dates.add(d);
      d = d.add(const Duration(days: 14));
    }
    return dates;
  }

  int get _currentPeriodIdx {
    final dates = _getPayDates();
    final now = DateTime.now();
    for (int i = 0; i < dates.length - 1; i++) {
      if (!now.isBefore(dates[i]) && now.isBefore(dates[i + 1])) return i;
    }
    return dates.isNotEmpty ? dates.length - 2 : 0;
  }

  DateTime get _periodStart {
    final dates = _getPayDates();
    final idx = (_currentPeriodIdx + _periodOffset).clamp(0, dates.length - 2);
    return dates[idx];
  }

  DateTime get _periodEnd => _periodStart.add(const Duration(days: 13));

  String get _periodLabel =>
      '${_dateFmt.format(_periodStart)} – ${_dateFmt.format(_periodEnd)}';

  // Next period helpers
  DateTime get _nextPeriodStart => _periodStart.add(const Duration(days: 14));
  DateTime get _nextPeriodEnd => _nextPeriodStart.add(const Duration(days: 13));
  String get _nextPeriodLabel =>
      '${_dateFmt.format(_nextPeriodStart)} – ${_dateFmt.format(_nextPeriodEnd)}';

  bool _canGoNext() {
    final dates = _getPayDates();
    final idx = _currentPeriodIdx + _periodOffset;
    return idx < dates.length - 2;
  }

  // ── Bill helpers ───────────────────────────────────────────────────────────

  bool _billInPeriod(Map bill, {DateTime? start, DateTime? end}) {
    final s = start ?? _periodStart;
    final e = end ?? _periodEnd;
    final dueDay = int.tryParse(bill['due_day']?.toString() ?? '');
    if (dueDay == null) return false;
    DateTime cur = DateTime(s.year, s.month, 1);
    while (!cur.isAfter(DateTime(e.year, e.month + 1, 1))) {
      try {
        final d = DateTime(cur.year, cur.month, dueDay);
        if (!d.isBefore(s) && !d.isAfter(e)) return true;
      } catch (_) {}
      cur = DateTime(cur.year, cur.month + 1, 1);
    }
    return false;
  }

  DateTime _billDueDate(Map bill, {DateTime? start, DateTime? end}) {
    final s = start ?? _periodStart;
    final e = end ?? _periodEnd;
    final dueDay = int.parse(bill['due_day'].toString());
    DateTime cur = DateTime(s.year, s.month, 1);
    while (true) {
      try {
        final d = DateTime(cur.year, cur.month, dueDay);
        if (!d.isBefore(s) && !d.isAfter(e)) return d;
      } catch (_) {}
      cur = DateTime(cur.year, cur.month + 1, 1);
      if (cur.isAfter(DateTime(e.year, e.month + 1, 1))) break;
    }
    return DateTime(s.year, s.month, dueDay);
  }

  // ── Data loading ───────────────────────────────────────────────────────────

  Future<void> _loadData() async {
    if (_refDate == null) return;
    setState(() {
      _loadingBills = true;
      _loadingTx = true;
    });

    // Determine which months the period spans
    final start = _periodStart;
    final end = _periodEnd;
    final months = <({int month, int year})>[
      (month: start.month, year: start.year),
    ];
    if (end.month != start.month || end.year != start.year) {
      months.add((month: end.month, year: end.year));
    }

    // Load bills from local storage (same source as Bills tab)
    try {
      final allLocal = await LocalBills.load();
      final seen = <dynamic>{};
      final allBills = <Map<String, dynamic>>[];
      for (final m in months) {
        for (final b in LocalBills.forMonth(allLocal, m.month, m.year)) {
          if (seen.add(b['id'])) allBills.add(b);
        }
      }
      if (mounted) setState(() { _bills = allBills; _loadingBills = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingBills = false);
    }

    // Load transactions
    try {
      final allTx = <Map<String, dynamic>>[];
      final seenTx = <dynamic>{};
      for (final m in months) {
        final fetched = await ApiService.getTransactions(m.month, m.year);
        for (final t in fetched) {
          if (seenTx.add(t['transaction_id'] ?? t['id'] ?? Object())) {
            allTx.add(t);
          }
        }
      }
      if (mounted) setState(() { _transactions = allTx; _loadingTx = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingTx = false);
    }
  }

  // ── Derived data ───────────────────────────────────────────────────────────

  List<Map<String, dynamic>> get _periodBills {
    return _bills.where((b) => _billInPeriod(b)).toList()
      ..sort((a, b) {
        final da = _billDueDate(a);
        final db = _billDueDate(b);
        return da.compareTo(db);
      });
  }

  double get _billsTotal => _periodBills.fold(
      0, (s, b) => s + (double.tryParse(b['amount']?.toString() ?? '0') ?? 0));

  List<Map<String, dynamic>> get _periodBillsNext {
    return _bills.where((b) => _billInPeriod(b, start: _nextPeriodStart, end: _nextPeriodEnd)).toList()
      ..sort((a, b) {
        final da = _billDueDate(a, start: _nextPeriodStart, end: _nextPeriodEnd);
        final db = _billDueDate(b, start: _nextPeriodStart, end: _nextPeriodEnd);
        return da.compareTo(db);
      });
  }

  double get _nextBillsTotal => _periodBillsNext.fold(
      0, (s, b) => s + (double.tryParse(b['amount']?.toString() ?? '0') ?? 0));

  List<Map<String, dynamic>> get _incomeTransactions {
    final start = _periodStart;
    final end = _periodEnd;
    return _transactions.where((t) {
      // Parse date
      final dateStr = t['date']?.toString() ?? '';
      DateTime? date;
      try {
        date = DateTime.parse(dateStr);
      } catch (_) {
        return false;
      }
      if (date.isBefore(start) || date.isAfter(end.add(const Duration(days: 1)))) return false;
      final amount = double.tryParse(t['amount']?.toString() ?? '0') ?? 0;
      final category = t['category']?.toString() ?? '';
      return amount < 0 || category == 'Income' || category == 'INCOME';
    }).toList();
  }

  double get _actualSpending {
    final start = _periodStart;
    final end = _periodEnd;
    return _transactions.where((t) {
      final dateStr = t['date']?.toString() ?? '';
      DateTime? date;
      try { date = DateTime.parse(dateStr); } catch (_) { return false; }
      if (date.isBefore(start) || date.isAfter(end.add(const Duration(days: 1)))) return false;
      final amt = double.tryParse(t['amount']?.toString() ?? '0') ?? 0;
      final cat = t['category']?.toString() ?? '';
      // Positive amounts are outgoing in Plaid; exclude income/transfer categories
      return amt > 0 &&
          cat != 'INCOME' && cat != 'Income' &&
          cat != 'TRANSFER_IN' && cat != 'Transfer In';
    }).fold(0.0, (s, t) => s + (double.tryParse(t['amount']?.toString() ?? '0') ?? 0));
  }

  double get _actualIncome {
    return _incomeTransactions.fold(0, (s, t) {
      final amt = double.tryParse(t['amount']?.toString() ?? '0') ?? 0;
      // Plaid income is typically negative (money in)
      return s + amt.abs();
    });
  }

  // ── Running balance rows ───────────────────────────────────────────────────

  List<_RunningRow> _buildRunningBalance() {
    final rows = <_RunningRow>[];
    // Pay date event
    rows.add(_RunningRow(
      date: _periodStart,
      label: _paycheckLabel.toUpperCase(),
      amount: _paycheckAmount,
      isPaycheck: true,
    ));
    // Bills
    for (final bill in _periodBills) {
      final amt = double.tryParse(bill['amount']?.toString() ?? '0') ?? 0;
      rows.add(_RunningRow(
        date: _billDueDate(bill),
        label: bill['name']?.toString() ?? '',
        amount: -amt,
        isPaycheck: false,
      ));
    }
    // Sort by date
    rows.sort((a, b) => a.date.compareTo(b.date));

    // Compute cumulative balance
    double running = 0;
    for (final r in rows) {
      running += r.amount;
      r.runningBalance = running;
    }
    return rows;
  }

  // ── UI ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(
        title: const Text('PAYCHECK'),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune),
            color: PC.gold,
            tooltip: 'Configure Paycheck',
            onPressed: _showConfigureSheet,
          ),
        ],
      ),
      body: _refDate == null ? _buildSetupPrompt() : _buildContent(),
    );
  }

  Widget _buildSetupPrompt() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Container(
          padding: const EdgeInsets.all(28),
          decoration: BoxDecoration(
            color: PC.card,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: PC.gold.withOpacity(0.3)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.payments_outlined, color: PC.gold, size: 52),
              const SizedBox(height: 16),
              const Text(
                'Paycheck Planner',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'Track your bi-weekly income against bills and see your running balance each pay period.',
                textAlign: TextAlign.center,
                style: TextStyle(color: PC.sage, fontSize: 13, height: 1.5),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: PC.gold,
                    foregroundColor: PC.background,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: const Icon(Icons.tune, size: 18),
                  label: const Text(
                    'CONFIGURE',
                    style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2),
                  ),
                  onPressed: _showConfigureSheet,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildContent() {
    return RefreshIndicator(
      color: PC.pink,
      backgroundColor: PC.surface,
      onRefresh: _loadData,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 48),
        children: [
          _buildPeriodNavigator(),
          const SizedBox(height: 14),
          _buildSummaryCard(),
          const SizedBox(height: 14),
          _buildBillsSection(),
          const SizedBox(height: 14),
          _buildAllocationBar(),
          const SizedBox(height: 14),
          _buildRunningBalanceSection(),
          const SizedBox(height: 14),
          _buildNextPeriodPreview(),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  // ── Period navigator ───────────────────────────────────────────────────────

  Widget _buildPeriodNavigator() {
    final atStart = (_currentPeriodIdx + _periodOffset) <= 0;
    final atEnd = !_canGoNext();

    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        IconButton(
          icon: const Icon(Icons.chevron_left),
          color: atStart ? PC.sage.withOpacity(0.3) : PC.sage,
          onPressed: atStart
              ? null
              : () {
                  setState(() => _periodOffset--);
                  _loadData();
                },
        ),
        Expanded(
          child: Column(
            children: [
              Text(
                _periodLabel,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'Bi-weekly · 14 days',
                style: TextStyle(color: PC.sage.withOpacity(0.7), fontSize: 11),
              ),
            ],
          ),
        ),
        IconButton(
          icon: const Icon(Icons.chevron_right),
          color: atEnd ? PC.sage.withOpacity(0.3) : PC.sage,
          onPressed: atEnd
              ? null
              : () {
                  setState(() => _periodOffset++);
                  _loadData();
                },
        ),
      ],
    );
  }

  // ── Summary card ───────────────────────────────────────────────────────────

  Widget _buildSummaryCard() {
    final projected = _paycheckAmount;
    final actual = _actualIncome;
    final diff = actual - projected;
    final bool loading = _loadingTx;

    Color diffColor;
    String diffLabel;
    IconData diffIcon;
    if (actual == 0 && loading) {
      diffColor = PC.sage;
      diffLabel = 'Loading...';
      diffIcon = Icons.hourglass_empty;
    } else if (diff.abs() < 1) {
      diffColor = PC.green;
      diffLabel = 'On track';
      diffIcon = Icons.check_circle_outline;
    } else if (diff > 0) {
      diffColor = PC.green;
      diffLabel = '+${_currFmt.format(diff.abs())} over';
      diffIcon = Icons.trending_up;
    } else {
      diffColor = PC.red;
      diffLabel = '${_currFmt.format(diff.abs())} under';
      diffIcon = Icons.trending_down;
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: _incomeCell('PROJECTED', _currFmt.format(projected), PC.gold)),
              Container(width: 1, height: 48, color: Colors.white10),
              Expanded(
                child: loading
                    ? _incomeCell('ACTUAL', 'Syncing...', PC.sage)
                    : _incomeCell('ACTUAL', _currFmt.format(actual), PC.green),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: diffColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: diffColor.withOpacity(0.3)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(diffIcon, color: diffColor, size: 15),
                const SizedBox(width: 6),
                Text(
                  diffLabel,
                  style: TextStyle(
                    color: diffColor,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _incomeCell(String label, String value, Color color) => Column(
        children: [
          Text(label,
              style: const TextStyle(
                  color: PC.sage, fontSize: 9, letterSpacing: 2)),
          const SizedBox(height: 6),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              value,
              style: TextStyle(
                  color: color, fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      );

  // ── Bills section ──────────────────────────────────────────────────────────

  Widget _buildBillsSection() {
    final bills = _periodBills;

    return Container(
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
            child: Row(
              children: [
                const Text(
                  'BILLS DUE',
                  style: TextStyle(
                      color: PC.sage,
                      fontSize: 10,
                      letterSpacing: 3,
                      fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                if (_loadingBills)
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: PC.pink),
                  ),
              ],
            ),
          ),
          if (bills.isEmpty && !_loadingBills)
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Text('No bills due this period.',
                  style: TextStyle(color: PC.sage, fontSize: 13)),
            )
          else
            ...bills.map((bill) => _billRow(bill)),
          if (bills.isNotEmpty)
            Container(
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: Colors.white10)),
              ),
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
              child: Row(
                children: [
                  const Text('TOTAL',
                      style: TextStyle(
                          color: PC.sage,
                          fontSize: 10,
                          letterSpacing: 2,
                          fontWeight: FontWeight.bold)),
                  const Spacer(),
                  Text(
                    _currFmt.format(_billsTotal),
                    style: const TextStyle(
                        color: PC.gold,
                        fontSize: 15,
                        fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _billRow(Map<String, dynamic> bill) {
    final amt = double.tryParse(bill['amount']?.toString() ?? '0') ?? 0;
    final due = _billDueDate(bill);
    return Container(
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: Colors.white10)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  bill['name']?.toString() ?? '',
                  style: const TextStyle(color: Colors.white, fontSize: 13),
                ),
                const SizedBox(height: 2),
                Text(
                  'Due ${_dateFmt.format(due)}',
                  style: const TextStyle(color: PC.sage, fontSize: 11),
                ),
              ],
            ),
          ),
          Text(
            _currFmt.format(amt),
            style: const TextStyle(
                color: PC.pink, fontSize: 14, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }

  // ── Allocation bar ─────────────────────────────────────────────────────────

  Widget _buildAllocationBar() {
    final spent = _loadingTx ? 0.0 : _actualSpending;
    final pct = _paycheckAmount > 0
        ? (spent / _paycheckAmount).clamp(0.0, 1.0)
        : 0.0;
    final pctDisplay = (_paycheckAmount > 0)
        ? (spent / _paycheckAmount * 100).clamp(0, 999).toStringAsFixed(1)
        : '0.0';
    final remaining = _paycheckAmount - spent;

    Color barColor;
    if (pct < 0.70) {
      barColor = PC.green;
    } else if (pct < 0.90) {
      barColor = PC.gold;
    } else {
      barColor = PC.red;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('SPENT THIS PERIOD',
                  style: TextStyle(
                      color: PC.sage,
                      fontSize: 10,
                      letterSpacing: 3,
                      fontWeight: FontWeight.bold)),
              const Spacer(),
              Text(
                _loadingTx ? 'Loading...' : '${_currFmt.format(spent)}  ($pctDisplay%)',
                style: TextStyle(
                    color: barColor,
                    fontSize: 12,
                    fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: pct,
              backgroundColor: PC.surface,
              valueColor: AlwaysStoppedAnimation<Color>(barColor),
              minHeight: 8,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Text('REMAINING',
                  style: TextStyle(
                      color: PC.sage, fontSize: 10, letterSpacing: 2)),
              const Spacer(),
              Text(
                _currFmt.format(remaining),
                style: TextStyle(
                  color: remaining >= 0 ? PC.green : PC.red,
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ── Running balance section ────────────────────────────────────────────────

  Widget _buildRunningBalanceSection() {
    final rows = _buildRunningBalance();

    return Container(
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(
        children: [
          GestureDetector(
            onTap: () => setState(() => _balanceExpanded = !_balanceExpanded),
            behavior: HitTestBehavior.opaque,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: Row(
                children: [
                  const Text(
                    'RUNNING BALANCE',
                    style: TextStyle(
                        color: PC.sage,
                        fontSize: 10,
                        letterSpacing: 3,
                        fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  Icon(
                    _balanceExpanded ? Icons.expand_less : Icons.expand_more,
                    color: PC.sage,
                    size: 20,
                  ),
                ],
              ),
            ),
          ),
          if (_balanceExpanded) ...[
            Container(height: 1, color: Colors.white10),
            ...rows.map((r) => _runningRow(r)),
          ],
        ],
      ),
    );
  }

  Widget _runningRow(_RunningRow r) {
    final amtColor = r.isPaycheck ? PC.green : PC.pink;
    final amtStr = r.isPaycheck
        ? '+${_currFmt.format(r.amount)}'
        : '−${_currFmt.format(r.amount.abs())}';
    final balColor = r.runningBalance >= 0 ? PC.sage : PC.red;

    return Container(
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: Colors.white10)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          // Left: amount + label
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  amtStr,
                  style: TextStyle(
                      color: amtColor,
                      fontSize: 13,
                      fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 2),
                Text(
                  r.label,
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          // Right: date + running balance
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                _dateFmt.format(r.date),
                style:
                    const TextStyle(color: PC.sage, fontSize: 11),
              ),
              const SizedBox(height: 2),
              Text(
                _currFmt.format(r.runningBalance),
                style: TextStyle(
                    color: balColor,
                    fontSize: 12,
                    fontWeight: FontWeight.bold),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ── Next period preview ────────────────────────────────────────────────────

  Widget _buildNextPeriodPreview() {
    return Container(
      decoration: BoxDecoration(
        color: PC.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: PC.grove.withOpacity(0.4)),
      ),
      child: Column(
        children: [
          GestureDetector(
            onTap: () =>
                setState(() => _nextPreviewExpanded = !_nextPreviewExpanded),
            behavior: HitTestBehavior.opaque,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: Row(
                children: [
                  const Icon(Icons.calendar_month_outlined,
                      color: PC.sage, size: 16),
                  const SizedBox(width: 8),
                  const Text(
                    'NEXT PAY PERIOD',
                    style: TextStyle(
                        color: PC.sage,
                        fontSize: 10,
                        letterSpacing: 3,
                        fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  Icon(
                    _nextPreviewExpanded
                        ? Icons.expand_less
                        : Icons.expand_more,
                    color: PC.sage,
                    size: 20,
                  ),
                ],
              ),
            ),
          ),
          if (_nextPreviewExpanded) ...[
            Container(height: 1, color: Colors.white10),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          _nextPeriodLabel,
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                              fontWeight: FontWeight.bold),
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          const Text('PROJECTED BILLS',
                              style: TextStyle(
                                  color: PC.sage, fontSize: 9, letterSpacing: 1)),
                          const SizedBox(height: 3),
                          Text(
                            _currFmt.format(_nextBillsTotal),
                            style: const TextStyle(
                                color: PC.gold,
                                fontSize: 15,
                                fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    ],
                  ),
                  if (_periodBillsNext.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    ..._periodBillsNext.map((bill) {
                      final amt =
                          double.tryParse(bill['amount']?.toString() ?? '0') ??
                              0;
                      final due = _billDueDate(bill,
                          start: _nextPeriodStart, end: _nextPeriodEnd);
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          children: [
                            const Icon(Icons.circle,
                                size: 5, color: PC.sage),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                bill['name']?.toString() ?? '',
                                style: const TextStyle(
                                    color: Colors.white70, fontSize: 12),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            Text(
                              _dateFmt.format(due),
                              style: const TextStyle(
                                  color: PC.sage, fontSize: 11),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              _currFmt.format(amt),
                              style: const TextStyle(
                                  color: PC.pink,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],
                ],
              ),
            ),
          ] else
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: Row(
                children: [
                  Text(
                    _nextPeriodLabel,
                    style:
                        const TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                  const Spacer(),
                  Text(
                    _currFmt.format(_nextBillsTotal),
                    style: const TextStyle(
                        color: PC.gold,
                        fontSize: 13,
                        fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  // ── Configure sheet ────────────────────────────────────────────────────────

  void _showConfigureSheet() {
    DateTime? selectedDate = _refDate;
    final amtCtrl = TextEditingController(
        text: _paycheckAmount > 0 ? _paycheckAmount.toStringAsFixed(2) : '');
    final labelCtrl =
        TextEditingController(text: _paycheckLabel == 'Paycheck' ? '' : _paycheckLabel);
    final selectedTxnIds = <String>{};

    showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) => Padding(
          padding: EdgeInsets.only(
            left: 20,
            right: 20,
            top: 20,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
          ),
          child: SingleChildScrollView(
            child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                children: [
                  const Icon(Icons.tune, color: PC.gold, size: 20),
                  const SizedBox(width: 10),
                  const Text(
                    'Configure Paycheck',
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close, color: PC.sage, size: 20),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Reference pay date
              const Text('REFERENCE PAY DATE',
                  style: TextStyle(
                      color: PC.sage,
                      fontSize: 9,
                      letterSpacing: 2,
                      fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              GestureDetector(
                onTap: () async {
                  final picked = await showDatePicker(
                    context: ctx,
                    initialDate: selectedDate ?? DateTime.now(),
                    firstDate: DateTime(2020),
                    lastDate: DateTime(2030),
                    builder: (context, child) => Theme(
                      data: Theme.of(context).copyWith(
                        colorScheme: const ColorScheme.dark(
                          primary: PC.gold,
                          surface: PC.card,
                          onSurface: Colors.white,
                        ),
                        dialogBackgroundColor: PC.surface,
                      ),
                      child: child!,
                    ),
                  );
                  if (picked != null) setSheet(() => selectedDate = picked);
                },
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 14),
                  decoration: BoxDecoration(
                    color: PC.card,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: Colors.white12),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.calendar_today,
                          color: PC.gold, size: 16),
                      const SizedBox(width: 10),
                      Text(
                        selectedDate != null
                            ? DateFormat('MMMM d, yyyy').format(selectedDate!)
                            : 'Tap to select a pay date',
                        style: TextStyle(
                            color: selectedDate != null
                                ? Colors.white
                                : PC.sage,
                            fontSize: 14),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Amount
              _sheetField(amtCtrl, 'Amount per paycheck',
                  const TextInputType.numberWithOptions(decimal: true)),
              const SizedBox(height: 12),

              // Label
              _sheetField(labelCtrl, 'Label (e.g. Avenue Five Res Payroll)',
                  TextInputType.text),

              // Or pick deposits — supports a paycheck split across banks
              if (_recentDeposits.isNotEmpty) ...[
                const SizedBox(height: 18),
                const Text('OR PICK YOUR DEPOSITS',
                    style: TextStyle(
                        color: PC.sage,
                        fontSize: 9,
                        letterSpacing: 2,
                        fontWeight: FontWeight.bold)),
                const SizedBox(height: 2),
                const Text(
                  'Tap every deposit that makes up your pay — Plutus adds them up.',
                  style: TextStyle(color: PC.sage, fontSize: 11),
                ),
                const SizedBox(height: 8),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 200),
                  child: ListView(
                    shrinkWrap: true,
                    children: _recentDeposits.take(20).map((t) {
                      final id =
                          (t['transaction_id'] ?? t['id'] ?? '').toString();
                      final amt = (double.tryParse(
                                  t['amount']?.toString() ?? '0') ??
                              0)
                          .abs();
                      final date =
                          DateTime.tryParse(t['date']?.toString() ?? '');
                      final label =
                          (t['merchant_name'] ?? t['name'] ?? 'Deposit')
                              .toString();
                      final acct = (t['account_name'] ?? '').toString();
                      final selected = selectedTxnIds.contains(id);
                      return ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(
                            selected
                                ? Icons.check_circle
                                : Icons.circle_outlined,
                            color: selected ? PC.gold : PC.sage,
                            size: 20),
                        onTap: (date == null || id.isEmpty)
                            ? null
                            : () {
                                setSheet(() {
                                  if (selected) {
                                    selectedTxnIds.remove(id);
                                  } else {
                                    selectedTxnIds.add(id);
                                  }
                                  double sum = 0;
                                  DateTime? latest;
                                  String onlyLabel = 'Paycheck';
                                  int n = 0;
                                  for (final dep in _recentDeposits) {
                                    final dId = (dep['transaction_id'] ??
                                            dep['id'] ??
                                            '')
                                        .toString();
                                    if (!selectedTxnIds.contains(dId)) {
                                      continue;
                                    }
                                    n++;
                                    sum += (double.tryParse(
                                                dep['amount']?.toString() ??
                                                    '0') ??
                                            0)
                                        .abs();
                                    final dd = DateTime.tryParse(
                                        dep['date']?.toString() ?? '');
                                    if (dd != null &&
                                        (latest == null ||
                                            dd.isAfter(latest))) {
                                      latest = dd;
                                    }
                                    onlyLabel = (dep['merchant_name'] ??
                                            dep['name'] ??
                                            'Paycheck')
                                        .toString();
                                  }
                                  if (selectedTxnIds.isNotEmpty) {
                                    amtCtrl.text = sum.toStringAsFixed(2);
                                    if (latest != null) selectedDate = latest;
                                    if (n == 1) labelCtrl.text = onlyLabel;
                                  }
                                });
                              },
                        title: Text(label,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                color: Colors.white, fontSize: 13)),
                        subtitle: Text(
                          [
                            if (date != null)
                              DateFormat('MMM d, yyyy').format(date),
                            if (acct.isNotEmpty) acct,
                          ].join('  ·  '),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style:
                              const TextStyle(color: PC.sage, fontSize: 11),
                        ),
                        trailing: Text('+${_currFmt.format(amt)}',
                            style: const TextStyle(
                                color: PC.green,
                                fontSize: 13,
                                fontWeight: FontWeight.bold)),
                      );
                    }).toList(),
                  ),
                ),
                if (selectedTxnIds.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    '${selectedTxnIds.length} deposit'
                    '${selectedTxnIds.length == 1 ? '' : 's'} selected — '
                    'total goes to the amount above',
                    style: const TextStyle(
                        color: PC.gold,
                        fontSize: 11,
                        fontWeight: FontWeight.bold),
                  ),
                ],
              ],
              const SizedBox(height: 24),

              // Save
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: PC.gold,
                    foregroundColor: PC.background,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  onPressed: () async {
                    if (selectedDate == null) return;
                    final amount = double.tryParse(amtCtrl.text) ?? 0;
                    final label = labelCtrl.text.trim().isEmpty
                        ? 'Paycheck'
                        : labelCtrl.text.trim();
                    Navigator.pop(ctx);
                    await _savePrefs(selectedDate!, amount, label);
                  },
                  child: const Text(
                    'SAVE',
                    style: TextStyle(
                        fontWeight: FontWeight.bold, letterSpacing: 2),
                  ),
                ),
              ),
            ],
          ),
          ),
        ),
      ),
    );
  }

  Widget _sheetField(
          TextEditingController ctrl, String label, TextInputType type) =>
      TextField(
        controller: ctrl,
        keyboardType: type,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: const TextStyle(color: PC.sage),
          filled: true,
          fillColor: PC.card,
          border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none),
          focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: PC.gold)),
        ),
      );
}

// ── Running balance data model ─────────────────────────────────────────────

class _RunningRow {
  final DateTime date;
  final String label;
  final double amount;
  final bool isPaycheck;
  double runningBalance = 0;

  _RunningRow({
    required this.date,
    required this.label,
    required this.amount,
    required this.isPaycheck,
  });
}
