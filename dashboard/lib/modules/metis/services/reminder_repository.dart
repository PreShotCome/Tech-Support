import 'package:flutter/foundation.dart';
import '../models/reminder.dart';
import 'database.dart';
import 'notification_service.dart';

/// Central in-memory store of reminders, backed by SQLite. Screens listen to
/// this so any mutation refreshes the whole UI.
class ReminderRepository extends ChangeNotifier {
  final _db = AppDatabase();
  final List<Reminder> _items = [];
  bool _loaded = false;

  bool get isLoaded => _loaded;

  List<Reminder> get pending {
    final list =
        _items.where((r) => r.status == ReminderStatus.pending).toList();
    list.sort((a, b) => a.dueAt.compareTo(b.dueAt));
    return list;
  }

  List<Reminder> get history {
    final list =
        _items.where((r) => r.status != ReminderStatus.pending).toList();
    list.sort((a, b) => b.dueAt.compareTo(a.dueAt));
    return list;
  }

  int get pendingCount => pending.length;
  int get overdueCount => _items.where((r) => r.isOverdue).length;
  int get completedCount =>
      _items.where((r) => r.status == ReminderStatus.completed).length;

  int get todayCount {
    final now = DateTime.now();
    final end = DateTime(now.year, now.month, now.day, 23, 59, 59);
    return pending.where((r) => !r.dueAt.isAfter(end)).length;
  }

  Future<void> load() async {
    _items
      ..clear()
      ..addAll(await _db.all());
    _loaded = true;
    notifyListeners();
  }

  // The database write is what persists a reminder; notifyListeners runs
  // before scheduling so the UI refreshes even if a notification fails.
  Future<Reminder> add(Reminder r) async {
    r.id = await _db.insert(r);
    _items.add(r);
    notifyListeners();
    await NotificationService.schedule(r);
    return r;
  }

  Future<void> save(Reminder r) async {
    await _db.update(r);
    final i = _items.indexWhere((e) => e.id == r.id);
    if (i >= 0) _items[i] = r;
    notifyListeners();
    await NotificationService.schedule(r);
  }

  Future<void> setStatus(Reminder r, ReminderStatus status) async {
    r.status = status;
    await _db.update(r);
    notifyListeners();
    if (status == ReminderStatus.pending) {
      await NotificationService.schedule(r);
    } else if (r.id != null) {
      await NotificationService.cancel(r.id!);
    }
  }

  Future<void> delete(Reminder r) async {
    if (r.id != null) {
      await _db.delete(r.id!);
      await NotificationService.cancel(r.id!);
    }
    _items.removeWhere((e) => e.id == r.id);
    notifyListeners();
  }

  /// True if a reminder with the same title and due time already exists —
  /// used to avoid creating duplicates when scanning Gmail repeatedly.
  bool exists(String title, DateTime dueAt) {
    return _items.any((r) =>
        r.title.toLowerCase() == title.toLowerCase() &&
        (r.dueAt.difference(dueAt).inMinutes).abs() < 1);
  }
}

final reminders = ReminderRepository();
