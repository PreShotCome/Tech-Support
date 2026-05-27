import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/reminder.dart';
import 'settings_store.dart';

/// Optional Claude API parsing.
///
/// Metis works fully offline via [HeuristicParser]; this is a *rare* fallback
/// used only when the user has supplied an API key, enabled it in Settings,
/// and the heuristic parser could not resolve a date/time on its own.
///
/// Dart has no official Anthropic SDK, so this calls the Messages API over
/// raw HTTP and constrains the reply with a JSON-schema structured output.
class ClaudeService {
  static const _endpoint = 'https://api.anthropic.com/v1/messages';
  static const _apiVersion = '2023-06-01';

  static const _systemPrompt =
      'You convert a short note into a scheduled reminder. '
      'Extract a concise imperative title and the absolute date/time it '
      'should fire. Resolve fuzzy phrases ("tomorrow morning", "in 20 '
      'minutes", "next Tuesday") against the supplied current time. '
      'If no time is stated, pick a sensible default (09:00 local) and set '
      'has_time to false. Return one reminder unless the note clearly '
      'contains several distinct tasks.';

  /// Returns the parsed reminder, or null if Claude could not be reached
  /// or returned nothing usable. Never throws.
  static Future<ParsedReminder?> parse(String raw) async {
    final results = await parseAll(raw);
    return results.isEmpty ? null : results.first;
  }

  /// Parses possibly several reminders out of a longer block of text
  /// (used for email scanning). Never throws — returns [] on any failure.
  static Future<List<ParsedReminder>> parseAll(String raw) async {
    if (!settings.claudeAvailable) return const [];

    final now = DateTime.now();
    try {
      final res = await http
          .post(
            Uri.parse(_endpoint),
            headers: {
              'content-type': 'application/json',
              'x-api-key': settings.claudeApiKey.trim(),
              'anthropic-version': _apiVersion,
            },
            body: jsonEncode({
              'model': settings.claudeModel,
              'max_tokens': 1024,
              'system': [
                {
                  'type': 'text',
                  'text': _systemPrompt,
                  'cache_control': {'type': 'ephemeral'},
                }
              ],
              'messages': [
                {
                  'role': 'user',
                  'content': 'Current local time: ${now.toIso8601String()}\n\n'
                      'Note to parse:\n$raw',
                }
              ],
              'output_config': {
                'format': {
                  'type': 'json_schema',
                  'schema': _schema,
                }
              },
            }),
          )
          .timeout(const Duration(seconds: 20));

      if (res.statusCode != 200) return const [];

      final body = jsonDecode(res.body) as Map<String, dynamic>;
      final content = body['content'] as List?;
      if (content == null || content.isEmpty) return const [];
      final text = content
          .whereType<Map>()
          .firstWhere((b) => b['type'] == 'text', orElse: () => {})['text'];
      if (text is! String) return const [];

      final parsed = jsonDecode(text) as Map<String, dynamic>;
      final items = parsed['reminders'] as List? ?? const [];
      return items.whereType<Map>().map(_toReminder).whereType<ParsedReminder>()
          .toList();
    } catch (_) {
      return const [];
    }
  }

  static ParsedReminder? _toReminder(Map item) {
    final title = (item['title'] as String?)?.trim();
    if (title == null || title.isEmpty) return null;
    final dtRaw = item['datetime'] as String?;
    DateTime? due;
    if (dtRaw != null && dtRaw.isNotEmpty) {
      due = DateTime.tryParse(dtRaw);
    }
    return ParsedReminder(
      title: title,
      dueAt: due,
      hasTime: item['has_time'] == true,
      notes: (item['notes'] as String?) ?? '',
    );
  }

  static const Map<String, Object> _schema = {
    'type': 'object',
    'additionalProperties': false,
    'required': ['reminders'],
    'properties': {
      'reminders': {
        'type': 'array',
        'items': {
          'type': 'object',
          'additionalProperties': false,
          'required': ['title', 'datetime', 'has_time', 'notes'],
          'properties': {
            'title': {'type': 'string'},
            'datetime': {
              'type': 'string',
              'description': 'ISO-8601 local datetime, or empty if none',
            },
            'has_time': {'type': 'boolean'},
            'notes': {'type': 'string'},
          },
        },
      },
    },
  };
}
