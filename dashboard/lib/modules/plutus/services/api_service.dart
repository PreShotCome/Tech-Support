import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'auth_service.dart';

class ApiService {
  static String _base = 'https://plutus-backend-production-4252.up.railway.app';

  static Future<void> setBaseUrl(String url) async {
    _base = url.replaceAll(RegExp(r'/$'), '');
    final p = await SharedPreferences.getInstance();
    await p.setString('backend_url', _base);
  }

  static Future<void> loadBaseUrl() async {
    final p = await SharedPreferences.getInstance();
    final saved = p.getString('backend_url');
    if (saved != null && saved.isNotEmpty) _base = saved;
  }

  static String get baseUrl => _base;

  /// Request headers, including the current Firebase ID token.
  static Future<Map<String, String>> _headers({bool json = false}) async {
    final token = await AuthService.idToken();
    return {
      if (json) 'Content-Type': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  // ── Generic helpers ──────────────────────────────────────────────────────

  static Future<dynamic> _get(String path, {Map<String, String>? params}) async {
    final uri = Uri.parse('$_base$path').replace(queryParameters: params);
    final res =
        await http.get(uri, headers: await _headers()).timeout(const Duration(seconds: 15));
    if (res.statusCode != 200) throw Exception('GET $path → ${res.statusCode}');
    return jsonDecode(res.body);
  }

  static Future<dynamic> _post(String path, Map<String, dynamic> body) async {
    final res = await http.post(
      Uri.parse('$_base$path'),
      headers: await _headers(json: true),
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 20));
    if (res.statusCode != 200) throw Exception('POST $path → ${res.statusCode}: ${res.body}');
    return jsonDecode(res.body);
  }

  static Future<dynamic> _put(String path, Map<String, dynamic> body) async {
    final res = await http.put(
      Uri.parse('$_base$path'),
      headers: await _headers(json: true),
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 15));
    if (res.statusCode != 200) throw Exception('PUT $path → ${res.statusCode}');
    return jsonDecode(res.body);
  }

  static Future<void> _delete(String path) async {
    final res = await http.delete(
      Uri.parse('$_base$path'),
      headers: await _headers(),
    ).timeout(const Duration(seconds: 15));
    if (res.statusCode != 200) throw Exception('DELETE $path → ${res.statusCode}');
  }

  // ── Plaid ────────────────────────────────────────────────────────────────

  static Future<String> createLinkToken() async {
    final data = await _post('/api/create_link_token', {});
    return data['link_token'] as String;
  }

  static Future<String> createUpdateLinkToken(String itemId) async {
    final data = await _post('/api/create_link_token', {'item_id': itemId});
    return data['link_token'] as String;
  }

  static Future<Map<String, dynamic>> exchangeToken(String publicToken) async {
    return await _post('/api/exchange_token', {'public_token': publicToken});
  }

  // ── Accounts ─────────────────────────────────────────────────────────────

  static Future<List<Map<String, dynamic>>> getAccounts() async {
    final data = await _get('/api/accounts');
    return List<Map<String, dynamic>>.from(data);
  }

  static Future<void> removeItem(String itemId) async {
    await _delete('/api/items/$itemId');
  }

  // ── Transactions ─────────────────────────────────────────────────────────

  static Future<List<Map<String, dynamic>>> getTransactions(int month, int year) async {
    final uri = Uri.parse('$_base/api/transactions').replace(queryParameters: {
      'month': month.toString(),
      'year': year.toString(),
    });
    final res =
        await http.get(uri, headers: await _headers()).timeout(const Duration(seconds: 30));
    if (res.statusCode != 200) throw Exception('GET /api/transactions → ${res.statusCode}');
    return List<Map<String, dynamic>>.from(jsonDecode(res.body));
  }

  static Future<void> setMerchantCategory(String merchant, String category) async {
    await _put('/api/merchant-category', {
      'merchant_name': merchant,
      'category': category,
    });
  }

  static Future<void> setTransactionCategory(String txnId, String category) async {
    await _put('/api/transactions/$txnId/category', {'category': category});
  }

  static Future<void> deleteMerchantCategoriesByCategory(String category) async {
    final res = await http.delete(
      Uri.parse('$_base/api/merchant-categories/by-category'),
      headers: await _headers(json: true),
      body: jsonEncode({'category': category}),
    ).timeout(const Duration(seconds: 15));
    if (res.statusCode != 200) throw Exception('DELETE by-category → ${res.statusCode}');
  }

  static Future<List<Map<String, dynamic>>> getMerchantCategories() async {
    final data = await _get('/api/merchant-categories');
    return List<Map<String, dynamic>>.from(data);
  }

  static Future<void> deleteMerchantCategory(String merchant) async {
    final res = await http.delete(
      Uri.parse('$_base/api/merchant-category'),
      headers: await _headers(json: true),
      body: jsonEncode({'merchant_name': merchant}),
    ).timeout(const Duration(seconds: 15));
    if (res.statusCode != 200) throw Exception('DELETE merchant-category → ${res.statusCode}');
  }

  // ── Bills ────────────────────────────────────────────────────────────────

  static Future<List<Map<String, dynamic>>> getBills(int month, int year) async {
    final data = await _get('/api/bills', params: {
      'month': month.toString(),
      'year': year.toString(),
    });
    return List<Map<String, dynamic>>.from(data);
  }

  static Future<Map<String, dynamic>> createBill({
    required String name,
    required double amount,
    int? dueDay,
    String category = 'Bill',
    String? accountId,
    String? merchantName,
  }) async {
    return await _post('/api/bills', {
      'name': name,
      'amount': amount,
      'due_day': dueDay,
      'category': category,
      'account_id': accountId,
      'merchant_name': merchantName,
    });
  }

  static Future<void> updateBill(int id, Map<String, dynamic> fields) async {
    await _put('/api/bills/$id', fields);
  }

  static Future<void> deleteBill(int id) async {
    await _delete('/api/bills/$id');
  }

  static Future<List<Map<String, dynamic>>> getRecurring() async {
    final data = await _get('/api/recurring');
    return List<Map<String, dynamic>>.from(data);
  }

  static Future<void> setBillPaid(int billId, int month, int year, bool paid) async {
    await _post('/api/bills/$billId/paid', {
      'month': month,
      'year': year,
      'paid': paid,
    });
  }

  // ── Stats ────────────────────────────────────────────────────────────────

  static Future<List<Map<String, dynamic>>> getStats(int month, int year) async {
    final data = await _get('/api/stats', params: {
      'month': month.toString(),
      'year': year.toString(),
    });
    return List<Map<String, dynamic>>.from(data);
  }

  // ── Income insights ──────────────────────────────────────────────────────

  static Future<Map<String, dynamic>> getIncomeInsights({int days = 90}) async {
    final data = await _get('/api/income-insights', params: {
      'days': days.toString(),
    });
    return Map<String, dynamic>.from(data);
  }

  // ── Sync ─────────────────────────────────────────────────────────────────

  static Future<Map<String, dynamic>> sync({bool full = false, int days = 90}) async {
    final data = await _post('/api/sync', {
      if (full) 'full': true,
      if (full) 'days': days,
    });
    return data is Map ? Map<String, dynamic>.from(data) : {};
  }

  // ── Manual Accounts ───────────────────────────────────────────────────────

  static Future<Map<String, dynamic>> createManualAccount({
    required String name,
    required String type,
    String subtype = '',
    double balance = 0,
    double creditLimit = 0,
  }) async {
    return await _post('/api/manual-accounts', {
      'name': name,
      'type': type,
      'subtype': subtype,
      'balance': balance,
      'credit_limit': creditLimit,
    });
  }

  static Future<void> updateManualAccount(String id, Map<String, dynamic> fields) async {
    await _put('/api/manual-accounts/$id', fields);
  }

  static Future<void> deleteManualAccount(String id) async {
    await _delete('/api/manual-accounts/$id');
  }

  // ── Health ───────────────────────────────────────────────────────────────

  static Future<bool> checkHealth() async {
    try {
      final res = await http.get(Uri.parse('$_base/health'), headers: await _headers())
          .timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
