import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Calls the Anthropic API with the user's own API key (BYOK).
///
/// The key is held only in device secure storage and sent straight to
/// Anthropic — it never touches the Plutus backend, so the app owner
/// pays nothing and never handles user keys.
class AiService {
  static const _storage = FlutterSecureStorage();
  static const _keyName = 'anthropic_api_key';

  // Haiku is the cheap default — the user is paying for their own usage.
  static const model = 'claude-haiku-4-5';

  static String? _key;

  static Future<void> loadKey() async {
    _key = await _storage.read(key: _keyName);
  }

  static Future<void> setKey(String key) async {
    final trimmed = key.trim();
    _key = trimmed;
    if (trimmed.isEmpty) {
      await _storage.delete(key: _keyName);
    } else {
      await _storage.write(key: _keyName, value: trimmed);
    }
  }

  static bool get hasKey => _key != null && _key!.isNotEmpty;

  static String get keyPreview {
    if (!hasKey) return '';
    final k = _key!;
    return k.length <= 8 ? '••••' : '••••••••${k.substring(k.length - 4)}';
  }

  /// Sends a conversation to Claude and returns the assistant's reply text.
  /// [messages] is an ordered list of `{role, content}` maps.
  static Future<String> chat({
    required String system,
    required List<Map<String, String>> messages,
    int maxTokens = 1024,
  }) async {
    if (!hasKey) throw Exception('No Anthropic API key set.');
    final res = await http
        .post(
          Uri.parse('https://api.anthropic.com/v1/messages'),
          headers: {
            'content-type': 'application/json',
            'x-api-key': _key!,
            'anthropic-version': '2023-06-01',
          },
          body: jsonEncode({
            'model': model,
            'max_tokens': maxTokens,
            'system': system,
            'messages': messages,
          }),
        )
        .timeout(const Duration(seconds: 60));

    if (res.statusCode != 200) throw Exception(_errorMessage(res));

    final data = jsonDecode(res.body);
    final content = data['content'];
    if (content is List) {
      final buf = StringBuffer();
      for (final block in content) {
        if (block is Map && block['type'] == 'text') buf.write(block['text']);
      }
      final text = buf.toString().trim();
      if (text.isNotEmpty) return text;
    }
    return 'Claude returned an empty response.';
  }

  /// Asks Claude to categorize a set of merchants. Returns validated
  /// `{merchant, category}` pairs (categories not in [categories] are dropped).
  static Future<List<Map<String, String>>> categorizeMerchants({
    required List<Map<String, String>> merchants,
    required List<String> categories,
  }) async {
    final list = merchants
        .map((m) => '- ${m['name']} (currently: ${m['current']})')
        .join('\n');
    final system =
        'You categorize bank-transaction merchants for a budgeting app. '
        'Allowed categories (use EXACTLY one, verbatim): '
        '${categories.join(', ')}. '
        'Respond with ONLY a JSON array and nothing else — no prose, no code '
        'fences. Each element is {"merchant": "<exact merchant name as given>", '
        '"category": "<one allowed category>"}. Choose the most accurate '
        'category for every merchant; if one is genuinely ambiguous use "Other".';
    final reply = await chat(
      system: system,
      messages: [{'role': 'user', 'content': 'Merchants:\n$list'}],
      maxTokens: 2000,
    );
    return _parseCategorizations(reply, categories);
  }

  static List<Map<String, String>> _parseCategorizations(
      String reply, List<String> categories) {
    final start = reply.indexOf('[');
    final end = reply.lastIndexOf(']');
    if (start < 0 || end <= start) return [];
    dynamic decoded;
    try {
      decoded = jsonDecode(reply.substring(start, end + 1));
    } catch (_) {
      return [];
    }
    if (decoded is! List) return [];
    final allowed = categories.toSet();
    final out = <Map<String, String>>[];
    for (final e in decoded) {
      if (e is Map) {
        final m = e['merchant']?.toString();
        final c = e['category']?.toString();
        if (m != null && c != null && m.isNotEmpty && allowed.contains(c)) {
          out.add({'merchant': m, 'category': c});
        }
      }
    }
    return out;
  }

  static String _errorMessage(http.Response res) {
    if (res.statusCode == 401) return 'Your Anthropic API key was rejected.';
    if (res.statusCode == 429) {
      return 'Anthropic rate limit reached — try again shortly.';
    }
    if (res.statusCode == 400) {
      try {
        final d = jsonDecode(res.body);
        return 'Anthropic error: ${d['error']?['message'] ?? res.body}';
      } catch (_) {}
    }
    return 'Anthropic request failed (${res.statusCode}).';
  }
}
