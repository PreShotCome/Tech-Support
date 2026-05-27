import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../models/safe_to_spend.dart';
import '../services/api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _fmt = NumberFormat.currency(symbol: '\$');
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  List<Map<String, dynamic>> _accounts = [];
  List<Map<String, dynamic>> _stats    = [];
  List<Map<String, dynamic>> _bills    = [];
  SafeToSpend? _sts;
  bool _loading = true;
  bool _syncing = false;
  String? _error;

  bool get _isCurrentMonth =>
      _month.month == DateTime.now().month &&
      _month.year == DateTime.now().year;

  @override
  void initState() {
    super.initState();
    _load();
    paycheckChanged.addListener(_load);
  }

  @override
  void dispose() {
    paycheckChanged.removeListener(_load);
    super.dispose();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final now = DateTime.now();
      final nextM = DateTime(now.year, now.month + 1, 1);
      final results = await Future.wait([
        ApiService.getAccounts(),
        ApiService.getStats(_month.month, _month.year),
        ApiService.getBills(_month.month, _month.year),
        ApiService.getBills(now.month, now.year),
        ApiService.getBills(nextM.month, nextM.year),
      ]);
      // Income insights are best-effort — the Safe-to-Spend card is optional.
      Map<String, dynamic> insights = {};
      try { insights = await ApiService.getIncomeInsights(); } catch (_) {}
      final p = await SharedPreferences.getInstance();
      final sts = SafeToSpend.compute(
        accounts: results[0],
        insights: insights,
        billsByMonth: {
          '${now.year}-${now.month}': results[3],
          '${nextM.year}-${nextM.month}': results[4],
        },
        taxEnabled: p.getBool('tax_setaside_enabled') ?? false,
        taxPct: p.getDouble('tax_setaside_pct') ?? 28.0,
        fallbackPayDate:
            SafeToSpend.nextPayDateFromRef(p.getInt('paycheck_ref_date_ms')),
      );
      if (mounted) setState(() {
        _accounts = results[0];
        _stats    = results[1];
        _bills    = results[2];
        _sts      = sts;
        _loading  = false;
      });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _sync() async {
    setState(() => _syncing = true);
    try {
      await ApiService.sync();
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Sync failed: $e'), backgroundColor: PC.card));
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  double get _totalIncome {
    double t = 0;
    for (final s in _stats) {
      final cat = s['category']?.toString() ?? '';
      if (cat == 'INCOME' || cat == 'Income' || cat == 'TRANSFER_IN') {
        t += (double.tryParse(s['category_total']?.toString() ?? '0') ?? 0).abs();
      }
    }
    return t;
  }

  double get _totalSpent {
    double t = 0;
    for (final s in _stats) {
      final v = double.tryParse(s['category_total']?.toString() ?? '0') ?? 0;
      if (v > 0) t += v;
    }
    return t;
  }

  double get _totalBills {
    double t = 0;
    for (final b in _bills) {
      if (b['paid'] != true) {
        t += double.tryParse(b['amount']?.toString() ?? '0') ?? 0;
      }
    }
    return t;
  }

  int get _billsPaid => _bills.where((b) => b['paid'] == true).length;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(
        title: const Text('PLUTUS'),
        actions: [
          IconButton(
            icon: _syncing
                ? const SizedBox(width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: PC.pink))
                : const Icon(Icons.sync),
            onPressed: _syncing ? null : _sync,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: PC.pink))
          : _error != null
              ? _errorView()
              : RefreshIndicator(
                  color: PC.pink,
                  backgroundColor: PC.surface,
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _monthPicker(),
                      const SizedBox(height: 16),
                      _summaryRow(),
                      const SizedBox(height: 16),
                      if (_isCurrentMonth && _sts != null) ...[
                        _safeToSpendCard(_sts!),
                        const SizedBox(height: 20),
                      ],
                      if (_stats.isNotEmpty) ...[
                        _sectionLabel('SPENDING BY CATEGORY'),
                        _categoryChart(),
                        const SizedBox(height: 20),
                      ],
                      Row(children: [
                        _sectionLabel('BILLS THIS MONTH'),
                        const Spacer(),
                        const Text('Tap bill on Bills tab to edit',
                            style: TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 1)),
                      ]),
                      _billsSummary(),
                      const SizedBox(height: 20),
                      _sectionLabel('ACCOUNTS'),
                      ..._accounts.map(_accountCard),
                      const SizedBox(height: 40),
                    ],
                  ),
                ),
    );
  }

  Widget _monthPicker() => Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      IconButton(
        icon: const Icon(Icons.chevron_left, color: PC.sage),
        onPressed: () {
          setState(() => _month = DateTime(_month.year, _month.month - 1));
          _load();
        },
      ),
      Text(DateFormat('MMMM yyyy').format(_month),
          style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
      IconButton(
        icon: const Icon(Icons.chevron_right, color: PC.sage),
        onPressed: _month.month == DateTime.now().month && _month.year == DateTime.now().year
            ? null
            : () {
                setState(() => _month = DateTime(_month.year, _month.month + 1));
                _load();
              },
      ),
    ],
  );

  Widget _summaryRow() => Column(children: [
    Row(children: [
      Expanded(child: _statCard('SPENT', _fmt.format(_totalSpent), PC.pink)),
      const SizedBox(width: 12),
      Expanded(child: _statCard('INCOME', _fmt.format(_totalIncome), PC.green)),
    ]),
    const SizedBox(height: 12),
    Row(children: [
      Expanded(child: _statCard('BILLS LEFT', _fmt.format(_totalBills), PC.gold)),
      const SizedBox(width: 12),
      Expanded(child: _statCard('PAID', '$_billsPaid/${_bills.length}', PC.sage)),
    ]),
  ]);

  Widget _statCard(String label, String value, Color color) => Container(
    padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
    decoration: BoxDecoration(
      color: PC.card,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: color.withOpacity(0.25)),
    ),
    child: Column(children: [
      FittedBox(fit: BoxFit.scaleDown, child: Text(label,
          maxLines: 1,
          style: TextStyle(color: color, fontSize: 9, letterSpacing: 2))),
      const SizedBox(height: 6),
      FittedBox(fit: BoxFit.scaleDown, child: Text(value,
          maxLines: 1,
          style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold))),
    ]),
  );

  Widget _safeToSpendCard(SafeToSpend s) {
    final safe = s.safeToSpend;
    final negative = safe < 0;
    final tight = !negative && s.dailyAllowance < 15;
    final tone = negative ? PC.red : tight ? PC.gold : PC.green;
    return GestureDetector(
      onTap: () => navRequest.value = 'safetospend',
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: PC.card,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: tone.withOpacity(0.4)),
        ),
        child: Row(children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('SAFE TO SPEND',
                    style: TextStyle(
                        color: PC.sage,
                        fontSize: 9,
                        letterSpacing: 2,
                        fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(_fmt.format(safe),
                      style: TextStyle(
                          color: tone,
                          fontSize: 26,
                          fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 4),
                Text(
                  negative
                      ? 'Hold off — short before next deposit'
                      : '${_fmt.format(s.dailyAllowance)}/day · ${s.daysUntilNextDeposit} days left',
                  style: const TextStyle(color: PC.sage, fontSize: 11),
                ),
              ],
            ),
          ),
          Icon(Icons.chevron_right, color: tone),
        ]),
      ),
    );
  }

  static const _catLabels = {
    'RENT_AND_UTILITIES':   'Rent & Utilities',
    'FOOD_AND_DRINK':       'Food & Drink',
    'GENERAL_MERCHANDISE':  'Shopping',
    'TRAVEL':               'Travel',
    'ENTERTAINMENT':        'Entertainment',
    'HEALTHCARE':           'Healthcare',
    'TRANSFER_OUT':         'Transfer Out',
    'LOAN_PAYMENTS':        'Loan Payments',
    'PERSONAL_CARE':        'Personal Care',
    'GENERAL_SERVICES':     'Services',
    'INCOME':               'Income',
    'GOVERNMENT_AND_NON_PROFIT': 'Government',
  };

  static String _label(String? raw) =>
      _catLabels[raw] ?? (raw ?? 'Other').replaceAll('_', ' ').toLowerCase()
          .split(' ').map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1)).join(' ');

  Widget _categoryChart() {
    // Exclude income/transfers — this is a spending chart
    final excludedCats = {'INCOME', 'Income', 'TRANSFER_IN', 'Transfer In', 'TRANSFER_OUT'};
    var cats = _stats.where((s) {
      final cat = s['category']?.toString() ?? '';
      final v = double.tryParse(s['category_total']?.toString() ?? '0') ?? 0;
      return v > 0 && s['category'] != null && !excludedCats.contains(cat);
    }).toList();

    // Sort largest first so the chart reads naturally
    cats.sort((a, b) {
      final av = double.tryParse(a['category_total'].toString()) ?? 0;
      final bv = double.tryParse(b['category_total'].toString()) ?? 0;
      return bv.compareTo(av);
    });

    if (cats.isEmpty) return const SizedBox();

    const colors = [PC.pink, PC.gold, PC.green, Colors.teal,
        Colors.purple, Colors.orange, Colors.blue, Color(0xFF80CBC4)];

    // Collapse everything past 6 into an "Other" bucket
    const maxSlices = 6;
    List<Map<String, dynamic>> shown = cats.length > maxSlices ? cats.sublist(0, maxSlices) : cats;
    double otherAmt = 0;
    if (cats.length > maxSlices) {
      for (final c in cats.sublist(maxSlices)) {
        otherAmt += double.tryParse(c['category_total'].toString()) ?? 0;
      }
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
        SizedBox(
          width: 130,
          height: 130,
          child: PieChart(PieChartData(
            sectionsSpace: 2,
            centerSpaceRadius: 32,
            sections: [
              ...List.generate(shown.length, (i) {
                final amt = double.tryParse(shown[i]['category_total'].toString()) ?? 0;
                return PieChartSectionData(
                  value: amt,
                  color: colors[i % colors.length],
                  radius: 42,
                  showTitle: false,
                );
              }),
              if (otherAmt > 0)
                PieChartSectionData(
                  value: otherAmt,
                  color: Colors.white24,
                  radius: 42,
                  showTitle: false,
                ),
            ],
          )),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              ...List.generate(shown.length, (i) {
                final c = shown[i];
                final color = colors[i % colors.length];
                final amt = double.tryParse(c['category_total'].toString()) ?? 0;
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(children: [
                    Container(width: 8, height: 8,
                        decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                    const SizedBox(width: 6),
                    Expanded(child: Text(_label(c['category']?.toString()),
                        style: const TextStyle(color: PC.sage, fontSize: 10),
                        overflow: TextOverflow.ellipsis)),
                    const SizedBox(width: 4),
                    Text(_fmt.format(amt),
                        style: const TextStyle(color: Colors.white, fontSize: 10)),
                  ]),
                );
              }),
              if (otherAmt > 0)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(children: [
                    Container(width: 8, height: 8,
                        decoration: BoxDecoration(color: Colors.white24, shape: BoxShape.circle)),
                    const SizedBox(width: 6),
                    const Expanded(child: Text('Other',
                        style: TextStyle(color: PC.sage, fontSize: 10))),
                    const SizedBox(width: 4),
                    Text(_fmt.format(otherAmt),
                        style: const TextStyle(color: Colors.white, fontSize: 10)),
                  ]),
                ),
            ],
          ),
        ),
      ]),
    );
  }

  Widget _billsSummary() => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: PC.card,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: Colors.white.withOpacity(0.06)),
    ),
    child: _bills.isEmpty
        ? const Center(child: Padding(
            padding: EdgeInsets.all(8),
            child: Text('No bills yet', style: TextStyle(color: PC.sage, fontSize: 13))))
        : Column(children: _bills.take(5).map((b) {
            final paid  = b['paid'] == true;
            final amt   = double.tryParse(b['amount']?.toString() ?? '0') ?? 0;
            final due   = b['due_day'];
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(children: [
                Icon(paid ? Icons.check_circle : Icons.radio_button_unchecked,
                    color: paid ? PC.green : PC.sage, size: 18),
                const SizedBox(width: 10),
                Expanded(child: Text(b['name'] ?? '',
                    style: TextStyle(
                        color: paid ? PC.sage : Colors.white,
                        decoration: paid ? TextDecoration.lineThrough : null,
                        decorationColor: PC.sage,
                        fontSize: 13))),
                if (due != null)
                  Text('Due $due', style: const TextStyle(color: PC.sage, fontSize: 11)),
                const SizedBox(width: 8),
                Text(_fmt.format(amt),
                    style: const TextStyle(color: PC.gold, fontSize: 13, fontWeight: FontWeight.bold)),
              ]),
            );
          }).toList()),
  );

  Widget _accountCard(Map<String, dynamic> a) {
    final type      = (a['type'] ?? '').toString().toLowerCase();
    final isCredit  = type == 'credit';
    final current   = double.tryParse(a['current_balance']?.toString() ?? '0') ?? 0;
    final available = double.tryParse(a['available_balance']?.toString() ?? '0') ?? 0;
    final limit     = double.tryParse(a['credit_limit']?.toString() ?? '0') ?? 0;
    final utiliz    = (limit > 0) ? (current / limit).clamp(0.0, 1.0) : 0.0;
    final utilizColor = utiliz > 0.7 ? PC.red : utiliz > 0.4 ? PC.gold : PC.green;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(isCredit ? Icons.credit_card : Icons.account_balance,
              color: PC.pink, size: 18),
          const SizedBox(width: 10),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(a['name'] ?? '',
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
              Text(a['institution_name'] ?? '',
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: PC.sage, fontSize: 11)),
            ],
          )),
        ]),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(isCredit ? 'BALANCE OWED' : 'AVAILABLE',
                style: const TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 1)),
            const SizedBox(height: 4),
            Text(_fmt.format(isCredit ? current : available),
                style: TextStyle(
                    color: isCredit ? PC.red : PC.green,
                    fontSize: 20, fontWeight: FontWeight.bold)),
          ])),
          if (isCredit && limit > 0)
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text('LIMIT ${_fmt.format(limit)}',
                  style: const TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 1)),
              const SizedBox(height: 4),
              Text('${(utiliz * 100).toStringAsFixed(0)}% used',
                  style: TextStyle(color: utilizColor, fontSize: 13)),
            ])),
        ]),
        if (isCredit && limit > 0) ...[
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: utiliz,
              backgroundColor: PC.surface,
              valueColor: AlwaysStoppedAnimation<Color>(utilizColor),
              minHeight: 6,
            ),
          ),
        ],
      ]),
    );
  }

  Widget _sectionLabel(String t) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Text(t, style: const TextStyle(
        color: PC.sage, fontSize: 11, letterSpacing: 3, fontWeight: FontWeight.bold)),
  );

  Widget _errorView() => Center(child: Padding(
    padding: const EdgeInsets.all(32),
    child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      Icon(Icons.cloud_off, size: 64, color: PC.pink.withOpacity(0.4)),
      const SizedBox(height: 16),
      const Text('Cannot reach backend', style: TextStyle(color: Colors.white, fontSize: 16)),
      const SizedBox(height: 8),
      Text(_error ?? '', style: const TextStyle(color: PC.sage, fontSize: 12),
          textAlign: TextAlign.center),
      const SizedBox(height: 24),
      ElevatedButton(
        style: ElevatedButton.styleFrom(backgroundColor: PC.pink, foregroundColor: PC.background),
        onPressed: _load,
        child: const Text('Retry'),
      ),
    ]),
  ));
}
