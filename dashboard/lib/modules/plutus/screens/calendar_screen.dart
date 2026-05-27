import 'package:device_calendar/device_calendar.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/timezone.dart' as tz;
import '../main.dart';
import '../services/api_service.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});
  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  final _calPlugin = DeviceCalendarPlugin();
  final _fmt = NumberFormat.currency(symbol: '\$');

  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  DateTime? _selected;
  DateTime? _refDate;
  double _paycheckAmount = 0;
  List<Map<String, dynamic>> _bills = [];
  bool _loading = false;
  bool _syncing = false;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _selected = DateTime(now.year, now.month, now.day);
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final p = await SharedPreferences.getInstance();
    final ms = p.getInt('paycheck_ref_date_ms');
    List<Map<String, dynamic>> bills = [];
    try {
      bills = await ApiService.getBills(_month.month, _month.year);
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _refDate = ms != null ? DateTime.fromMillisecondsSinceEpoch(ms) : null;
      _paycheckAmount = p.getDouble('paycheck_amount') ?? 0;
      _bills = bills;
      _loading = false;
    });
  }

  List<DateTime> _paydaysInMonth(DateTime month) {
    if (_refDate == null) return [];
    var d = DateTime(_refDate!.year, _refDate!.month, _refDate!.day);
    final monthStart = DateTime(month.year, month.month, 1);
    final monthEnd = DateTime(month.year, month.month + 1, 1);
    while (d.isAfter(monthStart.subtract(const Duration(days: 14)))) {
      d = d.subtract(const Duration(days: 14));
    }
    final results = <DateTime>[];
    while (d.isBefore(monthEnd)) {
      if (d.month == month.month && d.year == month.year) results.add(d);
      d = d.add(const Duration(days: 14));
    }
    return results;
  }

  List<_CalEvent> _eventsForDay(int day) {
    final events = <_CalEvent>[];
    for (final pd in _paydaysInMonth(_month)) {
      if (pd.day == day) {
        events.add(_CalEvent(_EvType.payday, 'Payday', _paycheckAmount > 0 ? _paycheckAmount : null));
      }
    }
    for (final b in _bills) {
      final dueDay = b['due_day'];
      if (dueDay != null && dueDay == day) {
        final amt = double.tryParse(b['amount']?.toString() ?? '0') ?? 0;
        final paid = b['paid'] == true;
        events.add(_CalEvent(
          paid ? _EvType.billPaid : _EvType.billDue,
          b['name']?.toString() ?? 'Bill',
          amt,
        ));
      }
    }
    return events;
  }

  Future<void> _syncToPhone() async {
    setState(() => _syncing = true);
    try {
      final permResult = await _calPlugin.requestPermissions();
      if (!(permResult.data ?? false)) {
        if (mounted) _snack('Calendar permission denied', isError: true);
        return;
      }
      final calsResult = await _calPlugin.retrieveCalendars();
      final writableCals = (calsResult.data ?? [])
          .where((c) => !(c.isReadOnly ?? true))
          .toList();
      if (writableCals.isEmpty) {
        if (mounted) _snack('No writable calendar found', isError: true);
        return;
      }
      final calId = writableCals.first.id!;
      int count = 0;

      // Sync paydays for ±1 month
      for (int mo = -1; mo <= 2; mo++) {
        final m = DateTime(_month.year, _month.month + mo);
        for (final pd in _paydaysInMonth(m)) {
          final start = tz.TZDateTime.utc(pd.year, pd.month, pd.day);
          final event = Event(calId,
            title: 'Payday${_paycheckAmount > 0 ? ' · ${_fmt.format(_paycheckAmount)}' : ''}',
            start: start,
            end: start.add(const Duration(hours: 1)),
            allDay: true,
          );
          final res = await _calPlugin.createOrUpdateEvent(event);
          if (res?.isSuccess == true) count++;
        }
      }

      // Sync current month bills
      for (final b in _bills) {
        final dueDay = b['due_day'] as int?;
        if (dueDay == null) continue;
        final dueDate = DateTime(_month.year, _month.month, dueDay);
        final amt = double.tryParse(b['amount']?.toString() ?? '0') ?? 0;
        final name = b['name']?.toString() ?? 'Bill';
        final paid = b['paid'] == true;
        final start = tz.TZDateTime.utc(dueDate.year, dueDate.month, dueDate.day);
        final event = Event(calId,
          title: '$name${paid ? ' ✓' : ''} · ${_fmt.format(amt)}',
          description: paid ? 'Paid' : 'Due',
          start: start,
          end: start.add(const Duration(hours: 1)),
          allDay: true,
        );
        final res = await _calPlugin.createOrUpdateEvent(event);
        if (res?.isSuccess == true) count++;
      }

      if (mounted) _snack('Synced $count events to calendar');
    } catch (e) {
      if (mounted) _snack('Sync failed: $e', isError: true);
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  void _snack(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: isError ? PC.red : PC.green,
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(
        title: const Text('CALENDAR'),
        actions: [
          IconButton(
            icon: _syncing
                ? const SizedBox(width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: PC.gold))
                : const Icon(Icons.sync_alt, color: PC.gold),
            tooltip: 'Sync to phone calendar',
            onPressed: _syncing ? null : _syncToPhone,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: PC.pink))
          : RefreshIndicator(
              color: PC.pink,
              backgroundColor: PC.surface,
              onRefresh: _load,
              child: CustomScrollView(
                slivers: [
                  SliverToBoxAdapter(child: Column(children: [
                    _monthHeader(),
                    const SizedBox(height: 4),
                    _weekDayRow(),
                    _grid(),
                    const Divider(color: Colors.white10, height: 1),
                  ])),
                  _dayDetailSliver(),
                ],
              ),
            ),
    );
  }

  Widget _monthHeader() => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      IconButton(
        icon: const Icon(Icons.chevron_left, color: PC.sage),
        onPressed: () {
          setState(() {
            _month = DateTime(_month.year, _month.month - 1);
            if (_selected?.month != _month.month || _selected?.year != _month.year) {
              _selected = DateTime(_month.year, _month.month, 1);
            }
          });
          _load();
        },
      ),
      Text(DateFormat('MMMM yyyy').format(_month),
          style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
      IconButton(
        icon: const Icon(Icons.chevron_right, color: PC.sage),
        onPressed: () {
          setState(() {
            _month = DateTime(_month.year, _month.month + 1);
            if (_selected?.month != _month.month || _selected?.year != _month.year) {
              _selected = DateTime(_month.year, _month.month, 1);
            }
          });
          _load();
        },
      ),
    ]),
  );

  Widget _weekDayRow() => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
    child: Row(
      children: ['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d) =>
        Expanded(child: Center(
          child: Text(d, style: const TextStyle(color: PC.sage, fontSize: 11,
              fontWeight: FontWeight.bold)),
        )),
      ).toList(),
    ),
  );

  Widget _grid() {
    final firstDay = DateTime(_month.year, _month.month, 1);
    final daysInMonth = DateTime(_month.year, _month.month + 1, 0).day;
    // ISO weekday: 1=Mon, 7=Sun → Sun offset = weekday % 7
    final startOffset = firstDay.weekday % 7;
    final today = DateTime.now();
    final paydays = _paydaysInMonth(_month).map((d) => d.day).toSet();

    final cells = <Widget>[];
    for (int i = 0; i < startOffset; i++) {
      cells.add(const SizedBox());
    }
    for (int day = 1; day <= daysInMonth; day++) {
      final events = _eventsForDay(day);
      final isToday = _month.year == today.year && _month.month == today.month && day == today.day;
      final isSelected = _selected != null &&
          _selected!.day == day &&
          _selected!.month == _month.month &&
          _selected!.year == _month.year;
      final isPayday = paydays.contains(day);

      cells.add(GestureDetector(
        onTap: () => setState(() =>
            _selected = DateTime(_month.year, _month.month, day)),
        child: Container(
          margin: const EdgeInsets.all(2),
          decoration: isSelected
              ? BoxDecoration(
                  color: PC.pink.withOpacity(0.18),
                  shape: BoxShape.circle,
                )
              : isToday
                  ? BoxDecoration(
                      border: Border.all(color: PC.pink.withOpacity(0.5), width: 1.5),
                      shape: BoxShape.circle,
                    )
                  : null,
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Text('$day',
                style: TextStyle(
                  color: isSelected ? PC.pink
                      : isToday ? PC.pinkBright
                      : isPayday ? PC.green
                      : Colors.white,
                  fontSize: 13,
                  fontWeight: isToday || isSelected || isPayday
                      ? FontWeight.bold : FontWeight.normal,
                )),
            if (events.isNotEmpty)
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                ...events.take(3).map((e) => Container(
                  width: 4, height: 4,
                  margin: const EdgeInsets.symmetric(horizontal: 1),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _evColor(e.type),
                  ),
                )),
              ]),
          ]),
        ),
      ));
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: GridView.count(
        crossAxisCount: 7,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        childAspectRatio: 1,
        children: cells,
      ),
    );
  }

  SliverList _dayDetailSliver() {
    final events = _selected != null
        ? _eventsForDay(_selected!.day)
        : <_CalEvent>[];

    final items = <Widget>[
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Text(
          _selected != null
              ? DateFormat('EEEE, MMMM d').format(_selected!)
              : 'Select a day',
          style: const TextStyle(color: PC.sage, fontSize: 12, letterSpacing: 1),
        ),
      ),
      if (events.isEmpty)
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 16),
          child: Text('No events', style: TextStyle(color: PC.sage, fontSize: 13)),
        )
      else
        ...events.map((e) => Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: PC.card,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _evColor(e.type).withOpacity(0.3)),
            ),
            child: Row(children: [
              Container(
                width: 10, height: 10,
                decoration: BoxDecoration(shape: BoxShape.circle, color: _evColor(e.type)),
              ),
              const SizedBox(width: 12),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(e.label,
                    style: const TextStyle(color: Colors.white, fontSize: 14,
                        fontWeight: FontWeight.bold)),
                Text(_evLabel(e.type),
                    style: TextStyle(color: _evColor(e.type), fontSize: 11)),
              ])),
              if (e.amount != null && e.amount! > 0)
                Text(_fmt.format(e.amount!),
                    style: TextStyle(color: _evColor(e.type),
                        fontWeight: FontWeight.bold, fontSize: 14)),
            ]),
          ),
        )),
      const SizedBox(height: 40),
    ];

    return SliverList(delegate: SliverChildListDelegate(items));
  }

  Color _evColor(_EvType t) {
    switch (t) {
      case _EvType.payday: return PC.green;
      case _EvType.billPaid: return PC.gold;
      case _EvType.billDue: return PC.red;
    }
  }

  String _evLabel(_EvType t) {
    switch (t) {
      case _EvType.payday: return 'Deposit expected';
      case _EvType.billPaid: return 'Paid';
      case _EvType.billDue: return 'Due';
    }
  }
}

enum _EvType { payday, billDue, billPaid }

class _CalEvent {
  final _EvType type;
  final String label;
  final double? amount;
  const _CalEvent(this.type, this.label, this.amount);
}
