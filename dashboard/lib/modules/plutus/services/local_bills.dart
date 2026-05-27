import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class LocalBills {
  static const _key = 'local_bills';

  static Future<List<Map<String, dynamic>>> load() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_key);
    if (raw == null) return [];
    return List<Map<String, dynamic>>.from(jsonDecode(raw));
  }

  static Future<void> _save(List<Map<String, dynamic>> bills) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_key, jsonEncode(bills));
  }

  // Returns bills with 'paid' field resolved for the given month/year
  static List<Map<String, dynamic>> forMonth(
      List<Map<String, dynamic>> all, int month, int year) {
    final key = '$year-$month';
    return all.map((b) {
      final pm = Map<String, dynamic>.from(b['paid_months'] ?? {});
      return Map<String, dynamic>.from(b)..['paid'] = pm[key] == true;
    }).toList();
  }

  static Future<List<Map<String, dynamic>>> create(
      Map<String, dynamic> fields) async {
    final bills = await load();
    bills.add({
      'id': 'lb_${DateTime.now().millisecondsSinceEpoch}',
      'name': fields['name'],
      'amount': fields['amount'],
      'due_day': fields['due_day'],
      'category': fields['category'] ?? 'Bill',
      'merchant_name': fields['merchant_name'],
      'paid_months': <String, dynamic>{},
    });
    await _save(bills);
    return bills;
  }

  static Future<List<Map<String, dynamic>>> update(
      String id, Map<String, dynamic> fields) async {
    final bills = await load();
    final idx = bills.indexWhere((b) => b['id'].toString() == id);
    if (idx >= 0) {
      bills[idx] = {...bills[idx], ...fields};
      await _save(bills);
    }
    return bills;
  }

  static Future<List<Map<String, dynamic>>> delete(String id) async {
    final bills = await load();
    bills.removeWhere((b) => b['id'].toString() == id);
    await _save(bills);
    return bills;
  }

  static Future<List<Map<String, dynamic>>> setPaid(
      String id, int month, int year, bool paid) async {
    final bills = await load();
    final key = '$year-$month';
    final idx = bills.indexWhere((b) => b['id'].toString() == id);
    if (idx >= 0) {
      final pm = Map<String, dynamic>.from(bills[idx]['paid_months'] ?? {});
      pm[key] = paid;
      bills[idx] = {...bills[idx], 'paid_months': pm};
      await _save(bills);
    }
    return bills;
  }

  // One-time migration from backend bills list
  static Future<void> migrateIfNeeded(
      List<Map<String, dynamic>> backendBills, int month, int year) async {
    final p = await SharedPreferences.getInstance();
    if (p.getString(_key) != null) return;
    final key = '$year-$month';
    final local = backendBills.map((b) => {
      'id': 'lb_${b['id']}',
      'name': b['name'],
      'amount': b['amount'],
      'due_day': b['due_day'],
      'category': b['category'] ?? 'Bill',
      'merchant_name': b['merchant_name'],
      'paid_months': b['paid'] == true ? {key: true} : <String, dynamic>{},
    }).toList();
    await _save(local);
  }
}
