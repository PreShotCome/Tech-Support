import '../models/reminder.dart';
import 'claude_service.dart';
import 'heuristic_parser.dart';
import 'settings_store.dart';

/// Orchestrates capture parsing.
///
/// The built-in [HeuristicParser] is always tried first and handles the vast
/// majority of captures with zero network use. Claude is consulted only as a
/// rare fallback — and only when the user has opted in — for a capture whose
/// time the heuristic parser could not pin down.
class ReminderParser {
  /// Parse a single voice/text capture into one reminder.
  static Future<ParsedReminder> parseCapture(String raw) async {
    final local = HeuristicParser.parse(raw);
    if (local.resolved) return local;

    if (settings.claudeAvailable) {
      final remote = await ClaudeService.parse(raw);
      if (remote != null && remote.resolved) return remote;
    }
    // Unresolved: caller asks the user to pick a time.
    return local;
  }

  /// Parse a longer block of text (e.g. an email body) into any number of
  /// reminders. Uses the heuristic parser per-sentence; if the user has
  /// enabled Claude, it is used for the whole block instead for better recall.
  static Future<List<ParsedReminder>> parseBlock(String raw) async {
    if (settings.claudeAvailable) {
      final remote = await ClaudeService.parseAll(raw);
      if (remote.isNotEmpty) return remote;
    }
    final out = <ParsedReminder>[];
    for (final sentence in raw.split(RegExp(r'[.\n!?]'))) {
      final s = sentence.trim();
      if (s.length < 6) continue;
      final p = HeuristicParser.parse(s);
      if (p.resolved) out.add(p);
    }
    return out;
  }
}
