/// A reminder captured by voice, text, or an email scan.

enum ReminderSource { voice, text, email }

enum ReminderStatus { pending, completed, dismissed }

ReminderSource _sourceFrom(String s) =>
    ReminderSource.values.firstWhere((e) => e.name == s,
        orElse: () => ReminderSource.text);

ReminderStatus _statusFrom(String s) =>
    ReminderStatus.values.firstWhere((e) => e.name == s,
        orElse: () => ReminderStatus.pending);

class Reminder {
  int? id;
  String title;
  String notes;
  DateTime dueAt;
  bool hasTime;
  ReminderSource source;
  ReminderStatus status;
  DateTime createdAt;
  String rawInput;

  Reminder({
    this.id,
    required this.title,
    this.notes = '',
    required this.dueAt,
    this.hasTime = true,
    this.source = ReminderSource.text,
    this.status = ReminderStatus.pending,
    DateTime? createdAt,
    this.rawInput = '',
  }) : createdAt = createdAt ?? DateTime.now();

  bool get isPending => status == ReminderStatus.pending;

  bool get isOverdue =>
      isPending && dueAt.isBefore(DateTime.now());

  Map<String, Object?> toMap() => {
        'id': id,
        'title': title,
        'notes': notes,
        'due_at': dueAt.millisecondsSinceEpoch,
        'has_time': hasTime ? 1 : 0,
        'source': source.name,
        'status': status.name,
        'created_at': createdAt.millisecondsSinceEpoch,
        'raw_input': rawInput,
      };

  factory Reminder.fromMap(Map<String, Object?> m) => Reminder(
        id: m['id'] as int?,
        title: m['title'] as String? ?? '',
        notes: m['notes'] as String? ?? '',
        dueAt: DateTime.fromMillisecondsSinceEpoch(m['due_at'] as int),
        hasTime: (m['has_time'] as int? ?? 1) == 1,
        source: _sourceFrom(m['source'] as String? ?? 'text'),
        status: _statusFrom(m['status'] as String? ?? 'pending'),
        createdAt:
            DateTime.fromMillisecondsSinceEpoch(m['created_at'] as int),
        rawInput: m['raw_input'] as String? ?? '',
      );
}

/// The structured result of parsing a raw capture into a reminder.
class ParsedReminder {
  final String title;
  final DateTime? dueAt;
  final bool hasTime;
  final String notes;

  /// True when a concrete date/time was confidently extracted.
  bool get resolved => dueAt != null;

  const ParsedReminder({
    required this.title,
    this.dueAt,
    this.hasTime = false,
    this.notes = '',
  });
}
