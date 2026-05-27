import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config.dart';

class ApiService {
  static final _headers = {
    'x-api-key': Config.apiKey,
    'Content-Type': 'application/json',
  };

  static Future<Map<String, dynamic>> getPortfolio() async {
    final r = await http.get(Uri.parse('${Config.apiBase}/portfolio'), headers: _headers);
    return jsonDecode(r.body);
  }

  static Future<List<dynamic>> getTrades() async {
    final r = await http.get(Uri.parse('${Config.apiBase}/trades'), headers: _headers);
    return jsonDecode(r.body)['trades'];
  }

  static Future<Map<String, dynamic>> getSettings() async {
    final r = await http.get(Uri.parse('${Config.apiBase}/settings'), headers: _headers);
    return jsonDecode(r.body);
  }

  static Future<void> updateSetting(String key, dynamic value) async {
    await http.post(
      Uri.parse('${Config.apiBase}/settings'),
      headers: _headers,
      body: jsonEncode({'key': key, 'value': value}),
    );
  }

  static Future<Map<String, dynamic>> togglePause() async {
    final r = await http.post(Uri.parse('${Config.apiBase}/pause'), headers: _headers);
    return jsonDecode(r.body);
  }

  static Future<Map<String, dynamic>> manualBuy(String ticker, double amount, String assetType) async {
    final r = await http.post(
      Uri.parse('${Config.apiBase}/buy'),
      headers: _headers,
      body: jsonEncode({'ticker': ticker, 'amount': amount, 'asset_type': assetType}),
    );
    return jsonDecode(r.body);
  }

  static Future<Map<String, dynamic>> manualSell(String ticker, double equity, String assetType) async {
    final r = await http.post(
      Uri.parse('${Config.apiBase}/sell'),
      headers: _headers,
      body: jsonEncode({'ticker': ticker, 'equity': equity, 'asset_type': assetType}),
    );
    return jsonDecode(r.body);
  }

  static Future<List<String>> getNeverList() async {
    final r = await http.get(Uri.parse('${Config.apiBase}/never'), headers: _headers);
    return List<String>.from(jsonDecode(r.body)['symbols']);
  }

  static Future<void> addNever(String symbol) async {
    await http.post(
      Uri.parse('${Config.apiBase}/never'),
      headers: _headers,
      body: jsonEncode({'symbol': symbol}),
    );
  }

  static Future<void> removeNever(String symbol) async {
    await http.delete(Uri.parse('${Config.apiBase}/never/$symbol'), headers: _headers);
  }

  static Future<List<dynamic>> getQueue() async {
    final r = await http.get(Uri.parse('${Config.apiBase}/queue'), headers: _headers);
    return jsonDecode(r.body)['queued'] ?? [];
  }

  static Future<void> queueOrder(String action, String ticker, double amount, String assetType) async {
    final r = await http.post(
      Uri.parse('${Config.apiBase}/queue'),
      headers: _headers,
      body: jsonEncode({
        'action':     action,
        'ticker':     ticker,
        'amount':     amount,
        'asset_type': assetType,
      }),
    );
    if (r.statusCode >= 400) {
      throw Exception(jsonDecode(r.body)['detail'] ?? 'Queue failed');
    }
  }

  static Future<void> cancelQueued(String id) async {
    await http.delete(Uri.parse('${Config.apiBase}/queue/$id'), headers: _headers);
  }

  static Future<String> chat(String message, int autonomyLevel) async {
    final r = await http.post(
      Uri.parse('${Config.apiBase}/chat'),
      headers: _headers,
      body: jsonEncode({'message': message, 'autonomy_level': autonomyLevel}),
    );
    if (r.statusCode == 200) {
      return jsonDecode(r.body)['reply'];
    }
    return 'AI chat unavailable — add Anthropic API key to enable.';
  }
}
