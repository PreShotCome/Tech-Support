/// Pure computation behind the Safe-to-Spend feature.
///
/// Given linked accounts, the backend income projection, and bills, it
/// works out how much can be spent right now without missing a bill
/// before the next deposit — and fences off a tax reserve on top.
library;

class DueBill {
  final String name;
  final double amount;
  final DateTime due;
  const DueBill(this.name, this.amount, this.due);
}

class SafeToSpend {
  final double availableCash;
  final double income30d;
  final double ytdIncome;
  final double taxReserve;
  final double taxPct;
  final bool taxEnabled;
  final double billsDueTotal;
  final List<DueBill> billsDueSoon;
  final DateTime? nextDepositDate;
  final bool projectionFromHistory;
  final bool hasManualSchedule;
  final double expectedDeposit;
  final int daysUntilNextDeposit;

  const SafeToSpend({
    required this.availableCash,
    required this.income30d,
    required this.ytdIncome,
    required this.taxReserve,
    required this.taxPct,
    required this.taxEnabled,
    required this.billsDueTotal,
    required this.billsDueSoon,
    required this.nextDepositDate,
    required this.projectionFromHistory,
    required this.hasManualSchedule,
    required this.expectedDeposit,
    required this.daysUntilNextDeposit,
  });

  double get safeToSpend => availableCash - billsDueTotal - taxReserve;

  double get dailyAllowance => daysUntilNextDeposit > 0
      ? safeToSpend / daysUntilNextDeposit
      : safeToSpend;

  static double _d(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;

  /// Next bi-weekly pay date after now, derived from a reference date —
  /// used as a projection fallback when there is no deposit history.
  static DateTime? nextPayDateFromRef(int? refMs) {
    if (refMs == null) return null;
    DateTime d = DateTime.fromMillisecondsSinceEpoch(refMs);
    final now = DateTime.now();
    while (!d.isAfter(now)) {
      d = d.add(const Duration(days: 14));
    }
    return d;
  }

  static SafeToSpend compute({
    required List<Map<String, dynamic>> accounts,
    required Map<String, dynamic> insights,
    required Map<String, List<Map<String, dynamic>>> billsByMonth,
    required bool taxEnabled,
    required double taxPct,
    DateTime? fallbackPayDate,
    double paycheckAmount = 0,
  }) {
    // Available cash — depository accounts only.
    double cash = 0;
    for (final a in accounts) {
      final type = (a['type'] ?? '').toString().toLowerCase();
      if (type == 'credit' || type == 'loan' || type == 'investment') continue;
      final avail = double.tryParse(a['available_balance']?.toString() ?? '');
      cash += avail ?? _d(a['current_balance']);
    }

    // A manually-set paycheck schedule wins over the backend auto-projection.
    DateTime? projected;
    final rawNext = insights['projected_next_date']?.toString();
    if (rawNext != null && rawNext.isNotEmpty) {
      try {
        projected = DateTime.parse(rawNext);
      } catch (_) {}
    }
    final hasManual = fallbackPayDate != null;
    final next = fallbackPayDate ?? projected;

    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    int days = 14;
    if (next != null) {
      final diff = next.difference(today).inDays;
      days = diff < 1 ? 1 : diff;
    }

    // Unpaid bills landing between today and the next deposit.
    final bills = <DueBill>[];
    if (next != null) {
      final unique = <dynamic, Map<String, dynamic>>{};
      for (final list in billsByMonth.values) {
        for (final b in list) {
          unique[b['id']] = b;
        }
      }
      for (final b in unique.values) {
        final dueDay = int.tryParse(b['due_day']?.toString() ?? '');
        if (dueDay == null) continue;
        final due = _nextDueDate(dueDay, today);
        if (due.isAfter(next)) continue;
        if (_isPaid(billsByMonth, b['id'], due)) continue;
        bills.add(DueBill(
            b['name']?.toString() ?? 'Bill', _d(b['amount']), due));
      }
      bills.sort((a, b) => a.due.compareTo(b.due));
    }
    final billsTotal = bills.fold(0.0, (s, b) => s + b.amount);

    final income30d = _d(insights['income_30d']);
    final ytd = _d(insights['ytd_income']);
    final reserve = taxEnabled ? income30d * (taxPct / 100) : 0.0;

    return SafeToSpend(
      availableCash: cash,
      income30d: income30d,
      ytdIncome: ytd,
      taxReserve: reserve,
      taxPct: taxPct,
      taxEnabled: taxEnabled,
      billsDueTotal: billsTotal,
      billsDueSoon: bills,
      nextDepositDate: next,
      projectionFromHistory: !hasManual && projected != null,
      hasManualSchedule: hasManual,
      expectedDeposit: (hasManual && paycheckAmount > 0)
          ? paycheckAmount
          : _d(insights['avg_deposit']),
      daysUntilNextDeposit: days,
    );
  }

  /// Next occurrence of a monthly due-day on or after [today].
  static DateTime _nextDueDate(int dueDay, DateTime today) {
    for (int m = 0; m < 4; m++) {
      final base = DateTime(today.year, today.month + m, 1);
      final daysInMonth = DateTime(base.year, base.month + 1, 0).day;
      final day = dueDay > daysInMonth ? daysInMonth : dueDay;
      final d = DateTime(base.year, base.month, day);
      if (!d.isBefore(today)) return d;
    }
    return DateTime(today.year, today.month + 4, dueDay > 28 ? 28 : dueDay);
  }

  static bool _isPaid(
      Map<String, List<Map<String, dynamic>>> billsByMonth,
      dynamic billId,
      DateTime due) {
    final list = billsByMonth['${due.year}-${due.month}'];
    if (list == null) return false;
    for (final b in list) {
      if (b['id'] == billId) return b['paid'] == true;
    }
    return false;
  }
}
