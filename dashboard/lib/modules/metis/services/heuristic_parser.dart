import '../models/reminder.dart';

/// Built-in natural-language parser. This is Metis's default and primary way
/// of turning a raw capture ("call mum tomorrow at 9", "in 20 minutes check
/// the oven") into a scheduled reminder — no network, no API key required.
class HeuristicParser {
  static const _leadIns = [
    "remind me to ", "remind me ", "reminder to ", "reminder: ", "reminder ",
    "remember to ", "remember ", "don't forget to ", "don't forget ",
    "i need to ", "i have to ", "i should ", "note to self: ",
    "note to self ", "note: ", "todo: ", "to do ",
  ];

  static const _weekdays = {
    'monday': 1, 'mon': 1,
    'tuesday': 2, 'tue': 2, 'tues': 2,
    'wednesday': 3, 'wed': 3,
    'thursday': 4, 'thu': 4, 'thur': 4, 'thurs': 4,
    'friday': 5, 'fri': 5,
    'saturday': 6, 'sat': 6,
    'sunday': 7, 'sun': 7,
  };

  static ParsedReminder parse(String raw) {
    final now = DateTime.now();
    var text = raw.trim();

    // Strip a leading command phrase ("remind me to ...").
    var lower = text.toLowerCase();
    for (final lead in _leadIns) {
      if (lower.startsWith(lead)) {
        text = text.substring(lead.length).trim();
        break;
      }
    }
    lower = text.toLowerCase();

    final cuts = <List<int>>[];
    void cut(Match? m) {
      if (m != null) cuts.add([m.start, m.end]);
    }

    // ── 1. Relative offsets ("in 20 minutes", "in 2 hours", "in a day") ──
    final relMin = RegExp(r'\bin (\d+)\s?(?:minutes?|mins?|m)\b').firstMatch(lower);
    final relHr  = RegExp(r'\bin (\d+)\s?(?:hours?|hrs?|h)\b').firstMatch(lower);
    final relDay = RegExp(r'\bin (\d+)\s?(?:days?)\b').firstMatch(lower);
    final relWk  = RegExp(r'\bin (\d+)\s?(?:weeks?)\b').firstMatch(lower);
    final relOne = RegExp(r'\bin an? (minute|hour|day|week)\b').firstMatch(lower);

    if (relMin != null) {
      cut(relMin);
      return _build(text, cuts,
          now.add(Duration(minutes: int.parse(relMin.group(1)!))), true);
    }
    if (relHr != null) {
      cut(relHr);
      return _build(text, cuts,
          now.add(Duration(hours: int.parse(relHr.group(1)!))), true);
    }
    if (relOne != null) {
      cut(relOne);
      final unit = relOne.group(1)!;
      final d = switch (unit) {
        'minute' => const Duration(minutes: 1),
        'hour' => const Duration(hours: 1),
        'day' => const Duration(days: 1),
        _ => const Duration(days: 7),
      };
      return _build(text, cuts, now.add(d), unit != 'day' && unit != 'week');
    }

    // ── 2. Day anchor ──
    DateTime? day; // date at midnight
    if (relDay != null) {
      cut(relDay);
      day = _midnight(now.add(Duration(days: int.parse(relDay.group(1)!))));
    } else if (relWk != null) {
      cut(relWk);
      day = _midnight(now.add(Duration(days: 7 * int.parse(relWk.group(1)!))));
    } else {
      final tomorrow = RegExp(r'\btomorrow\b').firstMatch(lower);
      final today = RegExp(r'\btoday\b').firstMatch(lower);
      final tonight = RegExp(r'\btonight\b').firstMatch(lower);
      final weekend = RegExp(r'\bthis weekend\b|\bthe weekend\b').firstMatch(lower);
      final weekday = RegExp(
              r'\b(next\s+)?(monday|mon|tuesday|tues?|wednesday|wed|thursday|thur?s?|friday|fri|saturday|sat|sunday|sun)\b')
          .firstMatch(lower);

      if (tomorrow != null) {
        cut(tomorrow);
        day = _midnight(now.add(const Duration(days: 1)));
      } else if (tonight != null) {
        cut(tonight);
        day = _midnight(now);
      } else if (today != null) {
        cut(today);
        day = _midnight(now);
      } else if (weekend != null) {
        cut(weekend);
        day = _midnight(_advanceToWeekday(now, 6, false));
      } else if (weekday != null) {
        cut(weekday);
        final isNext = weekday.group(1) != null;
        final wd = _weekdays[weekday.group(2)!]!;
        day = _midnight(_advanceToWeekday(now, wd, isNext));
      }
    }

    // ── 3. Clock time ──
    int? hour, minute;
    final atTime = RegExp(r'\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s?(am|pm)\b')
        .firstMatch(lower);
    final at24 = RegExp(r'\bat\s+(\d{1,2}):(\d{2})\b').firstMatch(lower);
    final noon = RegExp(r'\bnoon\b|\bmidday\b').firstMatch(lower);
    final midnight = RegExp(r'\bmidnight\b').firstMatch(lower);
    final morning = RegExp(r'\b(?:in the\s+)?morning\b').firstMatch(lower);
    final afternoon = RegExp(r'\b(?:in the\s+)?afternoon\b').firstMatch(lower);
    final evening = RegExp(r'\b(?:in the\s+)?evening\b').firstMatch(lower);

    if (atTime != null) {
      cut(atTime);
      var h = int.parse(atTime.group(1)!);
      final m = atTime.group(2) != null ? int.parse(atTime.group(2)!) : 0;
      final ap = atTime.group(3)!;
      if (ap == 'pm' && h != 12) h += 12;
      if (ap == 'am' && h == 12) h = 0;
      hour = h % 24;
      minute = m;
    } else if (at24 != null) {
      cut(at24);
      hour = int.parse(at24.group(1)!) % 24;
      minute = int.parse(at24.group(2)!) % 60;
    } else if (noon != null) {
      cut(noon);
      hour = 12;
      minute = 0;
    } else if (midnight != null) {
      cut(midnight);
      hour = 0;
      minute = 0;
    } else if (morning != null) {
      cut(morning);
      hour = 9;
      minute = 0;
    } else if (afternoon != null) {
      cut(afternoon);
      hour = 14;
      minute = 0;
    } else if (evening != null) {
      cut(evening);
      hour = 18;
      minute = 0;
    } else if (RegExp(r'\btonight\b').hasMatch(lower)) {
      hour = 20;
      minute = 0;
    }

    // ── 4. Assemble ──
    if (day == null && hour == null) {
      // Nothing time-like found — unresolved.
      return ParsedReminder(title: _title(text, cuts), dueAt: null);
    }

    final base = day ?? _midnight(now);
    final hasTime = hour != null;
    var due = DateTime(base.year, base.month, base.day, hour ?? 9, minute ?? 0);

    // If the time already passed and no explicit day was given, roll forward.
    if (day == null && due.isBefore(now)) {
      due = due.add(const Duration(days: 1));
    }

    return _build(text, cuts, due, hasTime);
  }

  static ParsedReminder _build(
      String text, List<List<int>> cuts, DateTime due, bool hasTime) {
    return ParsedReminder(
      title: _title(text, cuts),
      dueAt: due,
      hasTime: hasTime,
    );
  }

  static DateTime _midnight(DateTime d) => DateTime(d.year, d.month, d.day);

  static DateTime _advanceToWeekday(DateTime from, int weekday, bool next) {
    var days = (weekday - from.weekday) % 7;
    if (days <= 0) days += 7;
    if (next && days < 7) days += 7;
    return from.add(Duration(days: days));
  }

  /// Removes matched time phrases and tidies the remaining text into a title.
  static String _title(String text, List<List<int>> cuts) {
    if (cuts.isEmpty) return _tidy(text);
    cuts.sort((a, b) => a[0].compareTo(b[0]));
    final buf = StringBuffer();
    var pos = 0;
    for (final c in cuts) {
      if (c[0] > pos) buf.write(text.substring(pos, c[0]));
      if (c[1] > pos) pos = c[1];
    }
    if (pos < text.length) buf.write(text.substring(pos));
    return _tidy(buf.toString());
  }

  static String _tidy(String s) {
    var t = s.replaceAll(RegExp(r'\s+'), ' ').trim();
    // Drop dangling connector words left behind by the cut.
    t = t.replaceAll(RegExp(r'\b(at|on|by|the|in)\s*$', caseSensitive: false), '').trim();
    t = t.replaceAll(RegExp(r'^(at|on|by|to)\s+', caseSensitive: false), '').trim();
    if (t.isEmpty) return 'Reminder';
    return t[0].toUpperCase() + t.substring(1);
  }
}
