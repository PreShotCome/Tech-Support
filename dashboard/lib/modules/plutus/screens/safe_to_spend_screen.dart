import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../models/safe_to_spend.dart';
import '../services/api_service.dart';

/// Safe-to-Spend — built for irregular / gig / freelance income.
///
/// Answers one honest question: how much can I spend right now without
/// missing a bill before my next deposit lands? Also reserves a slice of
/// recent income for 1099 taxes so it never gets spent by accident.
class SafeToSpendScreen extends StatefulWidget {
  const SafeToSpendScreen({super.key});

  @override
  State<SafeToSpendScreen> createState() => _SafeToSpendScreenState();
}

class _SafeToSpendScreenState extends State<SafeToSpendScreen> {
  final _curr = NumberFormat.currency(symbol: '\$');
  final _dateFmt = DateFormat('EEE, MMM d');

  bool _loading = true;
  String? _error;

  List<Map<String, dynamic>> _accounts = [];
  Map<String, dynamic> _insights = {};
  final Map<String, List<Map<String, dynamic>>> _billsByMonth = {};

  // Tax set-aside config (SharedPreferences)
  bool _taxEnabled = false;
  double _taxPct = 28.0; // percent of income reserved for 1099 taxes
  int? _payRefMs; // manual paycheck reference date
  double _payAmount = 0; // manual paycheck amount

  @override
  void initState() {
    super.initState();
    _bootstrap();
    paycheckChanged.addListener(_bootstrap);
  }

  @override
  void dispose() {
    paycheckChanged.removeListener(_bootstrap);
    super.dispose();
  }

  Future<void> _bootstrap() async {
    final p = await SharedPreferences.getInstance();
    _taxEnabled = p.getBool('tax_setaside_enabled') ?? false;
    _taxPct = p.getDouble('tax_setaside_pct') ?? 28.0;
    _payRefMs = p.getInt('paycheck_ref_date_ms');
    _payAmount = p.getDouble('paycheck_amount') ?? 0;
    await _load();
  }

  // ── Data loading ───────────────────────────────────────────────────────────

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // Accounts are required; income insights are best-effort so the
      // screen still works if the backend has not deployed the endpoint.
      _accounts = await ApiService.getAccounts();
      try {
        _insights = await ApiService.getIncomeInsights();
      } catch (_) {
        _insights = {};
      }

      // Fetch bills for every month the projection window touches, so we
      // can read each bill's paid flag for the right month.
      final now = DateTime.now();
      final end = _projectedNextDate ?? now.add(const Duration(days: 21));
      _billsByMonth.clear();
      DateTime cur = DateTime(now.year, now.month, 1);
      final endMonth = DateTime(end.year, end.month, 1);
      while (!cur.isAfter(endMonth)) {
        final bills = await ApiService.getBills(cur.month, cur.year);
        _billsByMonth['${cur.year}-${cur.month}'] = bills;
        cur = DateTime(cur.year, cur.month + 1, 1);
      }

      if (mounted) setState(() => _loading = false);
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  DateTime? get _projectedNextDate {
    final raw = _insights['projected_next_date']?.toString();
    if (raw != null && raw.isNotEmpty) {
      try {
        return DateTime.parse(raw);
      } catch (_) {}
    }
    return SafeToSpend.nextPayDateFromRef(_payRefMs);
  }

  SafeToSpend get _model => SafeToSpend.compute(
        accounts: _accounts,
        insights: _insights,
        billsByMonth: _billsByMonth,
        taxEnabled: _taxEnabled,
        taxPct: _taxPct,
        fallbackPayDate: SafeToSpend.nextPayDateFromRef(_payRefMs),
        paycheckAmount: _payAmount,
      );

  // ── UI ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(
        title: const Text('SAFE TO SPEND'),
        actions: [
          IconButton(
            icon: const Icon(Icons.savings_outlined),
            color: PC.gold,
            tooltip: 'Tax set-aside',
            onPressed: _showTaxConfigSheet,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: PC.pink))
          : _error != null
              ? _errorView()
              : _accounts.isEmpty
                  ? _noAccountsView()
                  : _content(),
    );
  }

  Widget _content() {
    final s = _model;
    return RefreshIndicator(
      color: PC.pink,
      backgroundColor: PC.surface,
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 48),
        children: [
          _heroCard(s),
          const SizedBox(height: 14),
          _breakdownCard(s),
          const SizedBox(height: 14),
          _nextDepositCard(s),
          const SizedBox(height: 14),
          _billsDueCard(s),
          const SizedBox(height: 14),
          _taxCard(s),
          const SizedBox(height: 14),
          _incomeInsightsCard(s),
        ],
      ),
    );
  }

  // ── Hero ───────────────────────────────────────────────────────────────────

  Widget _heroCard(SafeToSpend s) {
    final safe = s.safeToSpend;
    final negative = safe < 0;
    final tight = !negative && s.dailyAllowance < 15;
    final Color tone = negative
        ? PC.red
        : tight
            ? PC.gold
            : PC.green;

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 26, horizontal: 20),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: tone.withOpacity(0.45)),
      ),
      child: Column(
        children: [
          const Text(
            'SAFE TO SPEND',
            style: TextStyle(
                color: PC.sage,
                fontSize: 10,
                letterSpacing: 3,
                fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 10),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              _curr.format(safe),
              style: TextStyle(
                  color: tone,
                  fontSize: 44,
                  fontWeight: FontWeight.bold,
                  letterSpacing: -1),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            negative
                ? "You're ${_curr.format(safe.abs())} short before your next deposit"
                : 'until ${_dateFmt.format(s.nextDepositDate ?? DateTime.now())}',
            textAlign: TextAlign.center,
            style: const TextStyle(color: PC.sage, fontSize: 12),
          ),
          const SizedBox(height: 18),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
            decoration: BoxDecoration(
              color: tone.withOpacity(0.12),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: tone.withOpacity(0.3)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.today_outlined, color: tone, size: 16),
                const SizedBox(width: 8),
                Text(
                  negative
                      ? 'Hold off on spending'
                      : '${_curr.format(s.dailyAllowance)} / day for ${s.daysUntilNextDeposit} days',
                  style: TextStyle(
                      color: tone,
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.5),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── Breakdown ──────────────────────────────────────────────────────────────

  Widget _breakdownCard(SafeToSpend s) {
    return _card(
      'HOW WE GOT THERE',
      Column(
        children: [
          _breakdownRow('Available cash', s.availableCash, PC.green),
          _breakdownRow('Bills before next deposit', -s.billsDueTotal, PC.pink),
          if (s.taxEnabled)
            _breakdownRow('Tax set-aside (${s.taxPct.toStringAsFixed(0)}%)',
                -s.taxReserve, PC.gold),
          const Divider(color: Colors.white12, height: 22),
          Row(
            children: [
              const Text('Safe to spend',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.bold)),
              const Spacer(),
              Text(
                _curr.format(s.safeToSpend),
                style: TextStyle(
                    color: s.safeToSpend < 0 ? PC.red : PC.green,
                    fontSize: 16,
                    fontWeight: FontWeight.bold),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _breakdownRow(String label, double value, Color color) {
    final sign = value < 0 ? '−' : '';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Expanded(
            child: Text(label,
                style: const TextStyle(color: PC.sage, fontSize: 13)),
          ),
          Text(
            '$sign${_curr.format(value.abs())}',
            style: TextStyle(
                color: color, fontSize: 14, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }

  // ── Next deposit ───────────────────────────────────────────────────────────

  Widget _nextDepositCard(SafeToSpend s) {
    final next = s.nextDepositDate;

    return _card(
      'NEXT DEPOSIT',
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (next == null)
            const Text(
              'Set your payday so Plutus can plan to it — or link a bank '
              'and it will estimate one from your deposits.',
              style: TextStyle(color: PC.sage, fontSize: 13, height: 1.4),
            )
          else ...[
            Row(
              children: [
                const Icon(Icons.event_available_outlined,
                    color: PC.green, size: 18),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    _dateFmt.format(next),
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  'in ${s.daysUntilNextDeposit} days',
                  style: const TextStyle(color: PC.sage, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              s.hasManualSchedule
                  ? 'Your bi-weekly paycheck'
                  : 'Estimated from your deposit history',
              style:
                  TextStyle(color: PC.sage.withOpacity(0.7), fontSize: 11),
            ),
            if (s.expectedDeposit > 0) ...[
              const SizedBox(height: 8),
              Text(
                '${s.hasManualSchedule ? 'Paycheck' : 'Typical deposit'}: '
                '${_curr.format(s.expectedDeposit)}',
                style: const TextStyle(color: PC.sage, fontSize: 12),
              ),
            ],
          ],
          const SizedBox(height: 12),
          GestureDetector(
            onTap: () {
              navRequest.value = 'paycheck';
              requestPaycheckConfig.value = true;
            },
            behavior: HitTestBehavior.opaque,
            child: Row(
              children: [
                const Icon(Icons.tune, color: PC.pink, size: 14),
                const SizedBox(width: 6),
                Text(
                  s.hasManualSchedule ? 'Change payday' : 'Set your payday',
                  style: const TextStyle(
                      color: PC.pink,
                      fontSize: 12,
                      fontWeight: FontWeight.bold),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── Bills due ──────────────────────────────────────────────────────────────

  Widget _billsDueCard(SafeToSpend s) {
    final bills = s.billsDueSoon;
    return _card(
      'BILLS BEFORE NEXT DEPOSIT',
      bills.isEmpty
          ? const Text('No bills due before your next deposit.',
              style: TextStyle(color: PC.sage, fontSize: 13))
          : Column(
              children: [
                ...bills.map((b) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        children: [
                          const Icon(Icons.receipt_long_outlined,
                              color: PC.pink, size: 16),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(b.name,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    color: Colors.white, fontSize: 13)),
                          ),
                          Text(_dateFmt.format(b.due),
                              style: const TextStyle(
                                  color: PC.sage, fontSize: 11)),
                          const SizedBox(width: 10),
                          Text(
                            _curr.format(b.amount),
                            style: const TextStyle(
                                color: PC.pink,
                                fontSize: 13,
                                fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    )),
                const Divider(color: Colors.white12, height: 22),
                Row(
                  children: [
                    const Text('TOTAL',
                        style: TextStyle(
                            color: PC.sage,
                            fontSize: 10,
                            letterSpacing: 2,
                            fontWeight: FontWeight.bold)),
                    const Spacer(),
                    Text(
                      _curr.format(s.billsDueTotal),
                      style: const TextStyle(
                          color: PC.pink,
                          fontSize: 15,
                          fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ],
            ),
    );
  }

  // ── Tax set-aside ──────────────────────────────────────────────────────────

  Widget _taxCard(SafeToSpend s) {
    final ytdTarget = s.ytdIncome * (s.taxPct / 100);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: PC.gold.withOpacity(0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.savings_outlined, color: PC.gold, size: 16),
              const SizedBox(width: 8),
              const Text('TAX SET-ASIDE',
                  style: TextStyle(
                      color: PC.sage,
                      fontSize: 10,
                      letterSpacing: 3,
                      fontWeight: FontWeight.bold)),
              const Spacer(),
              GestureDetector(
                onTap: _showTaxConfigSheet,
                child: Text(
                  s.taxEnabled
                      ? 'ON · ${s.taxPct.toStringAsFixed(0)}%'
                      : 'OFF',
                  style: TextStyle(
                      color: s.taxEnabled ? PC.gold : PC.sage,
                      fontSize: 11,
                      fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (!s.taxEnabled)
            const Text(
              '1099 / gig income? Turn this on to fence off a slice of every '
              'deposit for taxes so it never gets counted as spendable.',
              style: TextStyle(color: PC.sage, fontSize: 13, height: 1.4),
            )
          else ...[
            _taxRow('Reserved from last 30 days', s.taxReserve, PC.gold),
            const SizedBox(height: 8),
            _taxRow('Est. owed on income this year', ytdTarget, PC.sage),
            const SizedBox(height: 10),
            Text(
              'Keep ${_curr.format(s.taxReserve)} parked — it is already '
              'removed from your safe-to-spend total.',
              style: TextStyle(
                  color: PC.sage.withOpacity(0.8), fontSize: 11, height: 1.4),
            ),
          ],
        ],
      ),
    );
  }

  Widget _taxRow(String label, double value, Color color) => Row(
        children: [
          Expanded(
            child: Text(label,
                style: const TextStyle(color: PC.sage, fontSize: 13)),
          ),
          Text(
            _curr.format(value),
            style: TextStyle(
                color: color, fontSize: 14, fontWeight: FontWeight.bold),
          ),
        ],
      );

  // ── Income insights ────────────────────────────────────────────────────────

  Widget _incomeInsightsCard(SafeToSpend s) {
    final window = _insights['window_days']?.toString() ?? '90';
    final count = _insights['deposit_count']?.toString() ?? '0';
    final dailyRate =
        double.tryParse(_insights['daily_income_rate']?.toString() ?? '0') ?? 0;
    final gap = _insights['avg_gap_days'];

    return _card(
      'INCOME PATTERN · LAST $window DAYS',
      Column(
        children: [
          _insightRow('Deposits', count),
          _insightRow('Average income / day', _curr.format(dailyRate)),
          if (gap != null)
            _insightRow('Typical gap between deposits', '$gap days'),
          _insightRow('Earned last 30 days', _curr.format(s.income30d)),
        ],
      ),
    );
  }

  Widget _insightRow(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: Row(
          children: [
            Expanded(
              child: Text(label,
                  style: const TextStyle(color: PC.sage, fontSize: 13)),
            ),
            Text(value,
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.bold)),
          ],
        ),
      );

  // ── Shared bits ────────────────────────────────────────────────────────────

  Widget _card(String label, Widget child) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: PC.card,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white.withOpacity(0.06)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label,
                style: const TextStyle(
                    color: PC.sage,
                    fontSize: 10,
                    letterSpacing: 3,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            child,
          ],
        ),
      );

  Widget _noAccountsView() => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.account_balance_wallet_outlined,
                  size: 56, color: PC.pink.withOpacity(0.5)),
              const SizedBox(height: 16),
              const Text('No accounts linked',
                  style: TextStyle(color: Colors.white, fontSize: 16)),
              const SizedBox(height: 8),
              const Text(
                'Link a bank account on the Accounts tab so Plutus can see '
                'your income and bills.',
                textAlign: TextAlign.center,
                style: TextStyle(color: PC.sage, fontSize: 13, height: 1.5),
              ),
            ],
          ),
        ),
      );

  Widget _errorView() => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.cloud_off, size: 64, color: PC.pink.withOpacity(0.4)),
              const SizedBox(height: 16),
              const Text('Cannot reach backend',
                  style: TextStyle(color: Colors.white, fontSize: 16)),
              const SizedBox(height: 8),
              Text(_error ?? '',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: PC.sage, fontSize: 12)),
              const SizedBox(height: 24),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                    backgroundColor: PC.pink, foregroundColor: PC.background),
                onPressed: _load,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );

  // ── Tax config sheet ───────────────────────────────────────────────────────

  void _showTaxConfigSheet() {
    bool enabled = _taxEnabled;
    final pctCtrl = TextEditingController(text: _taxPct.toStringAsFixed(0));

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
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.savings_outlined, color: PC.gold, size: 20),
                  const SizedBox(width: 10),
                  const Text('Tax Set-Aside',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold)),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close, color: PC.sage, size: 20),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'For gig and 1099 income, taxes are not withheld for you. '
                'Plutus reserves this share of your last 30 days of income '
                'so it never shows up as money you can spend.',
                style: TextStyle(color: PC.sage, fontSize: 13, height: 1.5),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  const Text('Reserve for taxes',
                      style: TextStyle(color: Colors.white, fontSize: 14)),
                  const Spacer(),
                  Switch(
                    value: enabled,
                    activeColor: PC.gold,
                    onChanged: (v) => setSheet(() => enabled = v),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                controller: pctCtrl,
                enabled: enabled,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: 'Set-aside percentage',
                  suffixText: '%',
                  suffixStyle: const TextStyle(color: PC.sage),
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
              ),
              const SizedBox(height: 6),
              const Text(
                'A common rule of thumb for self-employed income is 25–30%.',
                style: TextStyle(color: PC.sage, fontSize: 11),
              ),
              const SizedBox(height: 20),
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
                    final pct = (double.tryParse(pctCtrl.text) ?? 28.0)
                        .clamp(0.0, 50.0)
                        .toDouble();
                    final p = await SharedPreferences.getInstance();
                    await p.setBool('tax_setaside_enabled', enabled);
                    await p.setDouble('tax_setaside_pct', pct);
                    if (mounted) {
                      setState(() {
                        _taxEnabled = enabled;
                        _taxPct = pct;
                      });
                    }
                    if (ctx.mounted) Navigator.pop(ctx);
                  },
                  child: const Text('SAVE',
                      style: TextStyle(
                          fontWeight: FontWeight.bold, letterSpacing: 2)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
