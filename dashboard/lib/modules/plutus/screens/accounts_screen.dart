import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:plaid_flutter/plaid_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../services/api_service.dart';

class AccountsScreen extends StatefulWidget {
  const AccountsScreen({super.key});
  @override
  State<AccountsScreen> createState() => _AccountsScreenState();
}

class _AccountsScreenState extends State<AccountsScreen> {
  final _fmt = NumberFormat.currency(symbol: '\$');
  List<Map<String, dynamic>> _accounts       = [];
  List<Map<String, dynamic>> _manualAccounts = [];
  bool _loading = true;
  bool _linking = false;

  StreamSubscription<LinkSuccess>? _successSub;
  StreamSubscription<LinkExit>?    _exitSub;
  StreamSubscription<LinkEvent>?   _eventSub;

  @override
  void initState() { super.initState(); _loadManualAccounts().then((_) => _load()); }

  @override
  void dispose() {
    _successSub?.cancel();
    _exitSub?.cancel();
    _eventSub?.cancel();
    super.dispose();
  }

  Future<void> _loadManualAccounts() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('manual_accounts');
    if (raw != null && mounted) {
      setState(() => _manualAccounts = List<Map<String, dynamic>>.from(jsonDecode(raw)));
    }
  }

  Future<void> _saveManualAccounts() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('manual_accounts', jsonEncode(_manualAccounts));
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final accounts = await ApiService.getAccounts();
      if (mounted) setState(() {
        _accounts = [...accounts, ..._manualAccounts];
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() {
        _accounts = [..._manualAccounts];
        _loading = false;
      });
    }
  }

  Future<void> _relinkBank(String itemId, String instName) async {
    _successSub?.cancel();
    _exitSub?.cancel();
    _eventSub?.cancel();

    setState(() => _linking = true);
    try {
      String token;
      bool isUpdateMode = false;
      try {
        token = await ApiService.createUpdateLinkToken(itemId);
        isUpdateMode = true;
      } catch (_) {
        token = await ApiService.createLinkToken();
      }

      await PlaidLink.create(configuration: LinkTokenConfiguration(token: token));

      _successSub = PlaidLink.onSuccess.listen((LinkSuccess event) async {
        _successSub?.cancel();
        _exitSub?.cancel();
        _eventSub?.cancel();
        try {
          if (!isUpdateMode && event.publicToken.isNotEmpty) {
            // Fresh link — exchange token, then remove the old expired item
            await ApiService.exchangeToken(event.publicToken);
            try { await ApiService.removeItem(itemId); } catch (_) {}
          }
          await _load();
          if (mounted) ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('$instName reconnected — run a Full Sync to restore transactions'),
              backgroundColor: PC.green,
              duration: const Duration(seconds: 5),
            ));
        } finally {
          if (mounted) setState(() => _linking = false);
        }
      });

      _exitSub = PlaidLink.onExit.listen((LinkExit event) {
        _successSub?.cancel();
        _exitSub?.cancel();
        _eventSub?.cancel();
        if (mounted) setState(() => _linking = false);
      });

      await PlaidLink.open();
    } catch (e) {
      _successSub?.cancel();
      _exitSub?.cancel();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: PC.red));
        setState(() => _linking = false);
      }
    }
  }

  Future<void> _connectBank() async {
    _successSub?.cancel();
    _exitSub?.cancel();
    _eventSub?.cancel();

    setState(() => _linking = true);
    try {
      final token = await ApiService.createLinkToken();

      await PlaidLink.create(configuration: LinkTokenConfiguration(token: token));

      _successSub = PlaidLink.onSuccess.listen((LinkSuccess event) async {
        _successSub?.cancel();
        _exitSub?.cancel();
        _eventSub?.cancel();
        try {
          await ApiService.exchangeToken(event.publicToken);
          await _load();
          if (mounted) ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Bank connected!'),
                backgroundColor: PC.green));
        } catch (e) {
          if (mounted) ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Connection error: $e'),
                backgroundColor: PC.red));
        } finally {
          if (mounted) setState(() => _linking = false);
        }
      });

      _exitSub = PlaidLink.onExit.listen((LinkExit event) {
        _successSub?.cancel();
        _exitSub?.cancel();
        _eventSub?.cancel();
        if (mounted) setState(() => _linking = false);
        if (event.error != null && mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('Link closed: ${event.error?.displayMessage ?? 'cancelled'}'),
            backgroundColor: PC.surface,
          ));
        }
      });

      await PlaidLink.open();
    } catch (e) {
      _successSub?.cancel();
      _exitSub?.cancel();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: PC.red));
        setState(() => _linking = false);
      }
    }
  }

  Future<void> _showManualAccountSheet([Map<String, dynamic>? existing]) async {
    final nameCtrl     = TextEditingController(text: existing?['name'] ?? '');
    final balCtrl      = TextEditingController(
        text: existing != null
            ? (double.tryParse(existing['current_balance']?.toString() ?? '0') ?? 0).toStringAsFixed(2)
            : '');
    final limitCtrl    = TextEditingController(
        text: existing != null
            ? (double.tryParse(existing['credit_limit']?.toString() ?? '0') ?? 0).toStringAsFixed(2)
            : '');
    final origCtrl     = TextEditingController(
        text: existing != null
            ? (double.tryParse(existing['loan_original_amount']?.toString() ?? '0') ?? 0) > 0
                ? (double.tryParse(existing['loan_original_amount'].toString()) ?? 0).toStringAsFixed(2)
                : ''
            : '');
    final paymentCtrl  = TextEditingController(
        text: existing != null
            ? (double.tryParse(existing['loan_payment']?.toString() ?? '0') ?? 0) > 0
                ? (double.tryParse(existing['loan_payment'].toString()) ?? 0).toStringAsFixed(2)
                : ''
            : '');
    final rateCtrl     = TextEditingController(
        text: existing != null
            ? (double.tryParse(existing['loan_rate']?.toString() ?? '0') ?? 0) > 0
                ? (double.tryParse(existing['loan_rate'].toString()) ?? 0).toStringAsFixed(2)
                : ''
            : '');
    final termCtrl     = TextEditingController(
        text: existing?['loan_term_months']?.toString() ?? '');
    String type = existing?['type'] ?? 'credit';
    final types = ['credit', 'loan', 'depository', 'investment', 'other'];
    final typeLabels = {
      'credit': 'Credit Card',
      'loan': 'Loan / Mortgage',
      'depository': 'Checking / Savings',
      'investment': 'Investment',
      'other': 'Other',
    };

    await showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.6,
        maxChildSize: 0.92,
        minChildSize: 0.4,
        builder: (_, ctrl) => StatefulBuilder(builder: (ctx, set) {
          final bal     = double.tryParse(balCtrl.text) ?? 0;
          final payment = double.tryParse(paymentCtrl.text) ?? 0;
          final monthsLeft = (bal > 0 && payment > 0) ? (bal / payment).ceil() : null;
          final payoffDate = monthsLeft != null
              ? DateTime(DateTime.now().year,
                  DateTime.now().month + monthsLeft)
              : null;

          return ListView(
            controller: ctrl,
            padding: EdgeInsets.only(
                left: 20, right: 20, top: 20,
                bottom: MediaQuery.of(ctx).viewInsets.bottom + 32),
            children: [
              Text(existing == null ? 'Add Manual Account' : 'Edit Account',
                  style: const TextStyle(color: Colors.white, fontSize: 18,
                      fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              const Text('For credit cards, loans, or any account not on Plaid.',
                  style: TextStyle(color: PC.sage, fontSize: 12)),
              const SizedBox(height: 20),
              _acctField(nameCtrl, 'Account name (e.g. "Home Mortgage")', TextInputType.text),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: type,
                dropdownColor: PC.card,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: 'Account type',
                  labelStyle: const TextStyle(color: PC.sage),
                  filled: true, fillColor: PC.card,
                  border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none),
                ),
                items: types.map((t) => DropdownMenuItem(
                    value: t,
                    child: Text(typeLabels[t] ?? t))).toList(),
                onChanged: (v) => set(() => type = v ?? type),
              ),
              const SizedBox(height: 12),
              // Credit fields
              if (type == 'credit') ...[
                Row(children: [
                  Expanded(child: _acctField(balCtrl, 'Balance owed',
                      const TextInputType.numberWithOptions(decimal: true))),
                  const SizedBox(width: 12),
                  Expanded(child: _acctField(limitCtrl, 'Credit limit',
                      const TextInputType.numberWithOptions(decimal: true))),
                ]),
              ],
              // Loan fields
              if (type == 'loan') ...[
                _acctField(balCtrl, 'Current balance owed',
                    const TextInputType.numberWithOptions(decimal: true)),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: _acctField(origCtrl, 'Original loan amount',
                      const TextInputType.numberWithOptions(decimal: true))),
                  const SizedBox(width: 12),
                  Expanded(child: TextField(
                    controller: rateCtrl,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: 'Interest rate (%)',
                      labelStyle: const TextStyle(color: PC.sage),
                      filled: true, fillColor: PC.card,
                      border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: BorderSide.none),
                      focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: PC.pink)),
                    ),
                    onChanged: (_) => set(() {}),
                  )),
                ]),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: TextField(
                    controller: paymentCtrl,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: 'Monthly payment',
                      labelStyle: const TextStyle(color: PC.sage),
                      filled: true, fillColor: PC.card,
                      border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: BorderSide.none),
                      focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: PC.pink)),
                    ),
                    onChanged: (_) => set(() {}),
                  )),
                  const SizedBox(width: 12),
                  Expanded(child: TextField(
                    controller: termCtrl,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: 'Term (months)',
                      hintText: 'e.g. 360',
                      hintStyle: const TextStyle(color: PC.sage, fontSize: 11),
                      labelStyle: const TextStyle(color: PC.sage),
                      filled: true, fillColor: PC.card,
                      border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: BorderSide.none),
                      focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: PC.pink)),
                    ),
                    onChanged: (_) => set(() {}),
                  )),
                ]),
                if (monthsLeft != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: PC.card,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: PC.green.withOpacity(0.3)),
                    ),
                    child: Row(children: [
                      const Icon(Icons.flag_outlined, color: PC.green, size: 16),
                      const SizedBox(width: 8),
                      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        const Text('EST. PAYOFF',
                            style: TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 2)),
                        const SizedBox(height: 2),
                        Text(
                          '$monthsLeft months · ${_fmt.format(bal)} ÷ ${_fmt.format(payment)}'
                          '\n${DateFormat('MMMM yyyy').format(payoffDate!)}',
                          style: const TextStyle(color: PC.green, fontSize: 12,
                              fontWeight: FontWeight.bold),
                        ),
                      ]),
                    ]),
                  ),
                ],
              ],
              // Other / depository / investment
              if (type != 'credit' && type != 'loan') ...[
                _acctField(balCtrl, 'Current balance',
                    const TextInputType.numberWithOptions(decimal: true)),
              ],
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity, height: 48,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                      backgroundColor: PC.pink, foregroundColor: PC.background,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12))),
                  onPressed: () async {
                    final name    = nameCtrl.text.trim();
                    final bal     = double.tryParse(balCtrl.text) ?? 0;
                    final limit   = double.tryParse(limitCtrl.text) ?? 0;
                    final orig    = double.tryParse(origCtrl.text) ?? 0;
                    final payment = double.tryParse(paymentCtrl.text) ?? 0;
                    final rate    = double.tryParse(rateCtrl.text) ?? 0;
                    final term    = int.tryParse(termCtrl.text) ?? 0;
                    if (name.isEmpty) return;
                    Navigator.pop(ctx);
                    final acctData = {
                      'name': name,
                      'type': type,
                      'subtype': '',
                      'current_balance': bal,
                      'available_balance': type == 'credit' && limit > 0 ? limit - bal : bal,
                      'credit_limit': limit,
                      'loan_original_amount': orig,
                      'loan_payment': payment,
                      'loan_rate': rate,
                      'loan_term_months': term,
                      'institution_name': 'Manual',
                      'item_id': '__manual__',
                      'source': 'manual',
                    };
                    if (existing == null) {
                      final newAcct = {'id': 'manual_${DateTime.now().millisecondsSinceEpoch}', ...acctData};
                      setState(() => _manualAccounts = [..._manualAccounts, newAcct]);
                    } else {
                      final updated = _manualAccounts.map((a) =>
                          a['id'] == existing['id'] ? {'id': a['id'], ...acctData} : a).toList();
                      setState(() => _manualAccounts = updated);
                    }
                    await _saveManualAccounts();
                    await _load();
                    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                      content: Text(existing == null ? 'Account added!' : 'Account updated!'),
                      backgroundColor: PC.green,
                    ));
                  },
                  child: Text(existing == null ? 'ADD ACCOUNT' : 'SAVE CHANGES',
                      style: const TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2)),
                ),
              ),
            ],
          );
        }),
      ),
    );
  }

  Widget _acctField(TextEditingController ctrl, String label, TextInputType type) =>
      TextField(
        controller: ctrl,
        keyboardType: type,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: const TextStyle(color: PC.sage),
          filled: true, fillColor: PC.card,
          border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
          focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: PC.pink)),
        ),
      );

  Future<void> _removeManualAccount(String id, String name) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: PC.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Remove Account', style: TextStyle(color: Colors.white)),
        content: Text('Remove "$name" from Plutus?',
            style: const TextStyle(color: PC.sage)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel', style: TextStyle(color: PC.sage))),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: PC.red, foregroundColor: Colors.white),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (ok == true) {
      setState(() => _manualAccounts = _manualAccounts.where((a) => a['id'] != id).toList());
      await _saveManualAccounts();
      await _load();
    }
  }

  Future<void> _removeItem(String itemId, String instName) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: PC.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Remove Bank', style: TextStyle(color: Colors.white)),
        content: Text(
            'Remove $instName and all its accounts from Plutus?\n\nThis cannot be undone.',
            style: const TextStyle(color: PC.sage)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: PC.sage)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: PC.red, foregroundColor: Colors.white),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (ok == true) {
      try {
        await ApiService.removeItem(itemId);
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Bank removed'),
              backgroundColor: PC.green));
        await _load();
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Remove failed: $e'),
              backgroundColor: PC.red));
      }
    }
  }

  Map<String, List<Map<String, dynamic>>> get _grouped {
    final map = <String, List<Map<String, dynamic>>>{};
    for (final a in _accounts) {
      final key = a['item_id'] ?? 'unknown';
      (map[key] ??= []).add(a);
    }
    return map;
  }

  bool _isManual(Map<String, dynamic> a) =>
      a['item_id'] == '__manual__' || a['source'] == 'manual';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(
        title: const Text('ACCOUNTS'),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit_note),
            color: PC.gold,
            tooltip: 'Add Manual Account',
            onPressed: _showManualAccountSheet,
          ),
          IconButton(
            icon: _linking
                ? const SizedBox(width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: PC.pink))
                : const Icon(Icons.add_card),
            color: PC.pink,
            tooltip: 'Connect via Plaid',
            onPressed: _linking ? null : _connectBank,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: PC.pink))
          : _accounts.isEmpty
              ? _empty()
              : RefreshIndicator(
                  color: PC.pink,
                  backgroundColor: PC.surface,
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      ..._grouped.entries.expand((entry) {
                        final itemId   = entry.key;
                        final accounts = entry.value;
                        final isManual = accounts.any(_isManual);
                        final instName = isManual
                            ? 'Manual Accounts'
                            : (accounts.first['institution_name'] ?? 'Bank');
                        return [
                          _instHeader(itemId, instName, isManual: isManual,
                              accounts: accounts),
                          ...accounts.map(_accountCard),
                          const SizedBox(height: 8),
                        ];
                      }),
                      const SizedBox(height: 40),
                    ],
                  ),
                ),
    );
  }

  Widget _instHeader(String itemId, String name,
      {bool isManual = false, List<Map<String, dynamic>> accounts = const []}) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          Expanded(child: Text(name.toUpperCase(),
              style: const TextStyle(
                  color: PC.sage, fontSize: 11, letterSpacing: 3,
                  fontWeight: FontWeight.bold),
              overflow: TextOverflow.ellipsis)),
          const SizedBox(width: 8),
          if (!isManual) ...[
            TextButton.icon(
              style: TextButton.styleFrom(
                foregroundColor: PC.sage,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                side: BorderSide(color: PC.sage.withOpacity(0.4), width: 1),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: _linking ? null : () => _relinkBank(itemId, name),
              icon: _linking
                  ? const SizedBox(width: 12, height: 12,
                      child: CircularProgressIndicator(strokeWidth: 2, color: PC.sage))
                  : const Icon(Icons.sync, size: 14),
              label: const Text('Relink', style: TextStyle(fontSize: 11)),
            ),
            const SizedBox(width: 6),
            TextButton.icon(
              style: TextButton.styleFrom(
                foregroundColor: PC.red,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                side: const BorderSide(color: PC.red, width: 1),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: () => _removeItem(itemId, name),
              icon: const Icon(Icons.link_off, size: 14),
              label: const Text('Remove', style: TextStyle(fontSize: 11)),
            ),
          ],
        ]),
      );

  Widget _accountCard(Map<String, dynamic> a) {
    final type      = (a['type'] ?? '').toString().toLowerCase();
    final subtype   = (a['subtype'] ?? '').toString();
    final isCredit  = type == 'credit';
    final isLoan    = type == 'loan';
    final current   = double.tryParse(a['current_balance']?.toString() ?? '0') ?? 0;
    final available = double.tryParse(a['available_balance']?.toString() ?? '0') ?? 0;
    final limit     = double.tryParse(a['credit_limit']?.toString() ?? '0') ?? 0;
    final utiliz    = (limit > 0) ? (current / limit).clamp(0.0, 1.0) : 0.0;
    final utilizColor = utiliz > 0.7 ? PC.red : utiliz > 0.4 ? PC.gold : PC.green;

    final isManual = _isManual(a);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isManual
            ? PC.gold.withOpacity(0.2)
            : Colors.white.withOpacity(0.06)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(_accountIcon(type, subtype), color: isManual ? PC.gold : PC.pink, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Expanded(child: Text(a['name'] ?? '',
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontSize: 14,
                        fontWeight: FontWeight.bold))),
                if (isManual) ...[
                  GestureDetector(
                    onTap: () => _showManualAccountSheet(a),
                    child: const Padding(
                      padding: EdgeInsets.only(left: 8),
                      child: Icon(Icons.edit_outlined, size: 16, color: PC.gold),
                    ),
                  ),
                  GestureDetector(
                    onTap: () => _removeManualAccount(
                        a['id'].toString(), a['name'] ?? ''),
                    child: const Padding(
                      padding: EdgeInsets.only(left: 8),
                      child: Icon(Icons.delete_outline, size: 16, color: PC.red),
                    ),
                  ),
                ],
              ]),
              if (a['official_name'] != null && a['official_name'] != a['name'])
                Text(a['official_name'],
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: PC.sage, fontSize: 10)),
            ],
          )),
        ]),
        const SizedBox(height: 16),

        if (isCredit) ...[
          Row(children: [
            Expanded(child: _balanceCol('BALANCE OWED', _fmt.format(current), PC.red)),
            if (limit > 0) ...[
              Expanded(child: _balanceCol('CREDIT LIMIT', _fmt.format(limit), PC.sage)),
              Expanded(child: _balanceCol('AVAILABLE', _fmt.format(available), PC.green)),
            ],
          ]),
          if (limit > 0) ...[
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                    value: utiliz,
                    backgroundColor: PC.surface,
                    valueColor: AlwaysStoppedAnimation<Color>(utilizColor),
                    minHeight: 6),
              )),
              const SizedBox(width: 8),
              Text('${(utiliz * 100).toStringAsFixed(0)}%',
                  style: TextStyle(color: utilizColor, fontSize: 11)),
            ]),
          ],
        ] else if (isLoan) ...[
          Row(children: [
            Expanded(child: _balanceCol('BALANCE OWED', _fmt.format(current), PC.red)),
            if ((a['loan_original_amount'] ?? 0) > 0)
              Expanded(child: _balanceCol('ORIGINAL',
                  _fmt.format(double.tryParse(a['loan_original_amount'].toString()) ?? 0),
                  PC.sage)),
            if ((a['loan_payment'] ?? 0) > 0)
              Expanded(child: _balanceCol('MONTHLY PMT',
                  _fmt.format(double.tryParse(a['loan_payment'].toString()) ?? 0),
                  PC.gold)),
          ]),
          if ((a['loan_rate'] ?? 0) > 0 || (a['loan_term_months'] ?? 0) > 0) ...[
            const SizedBox(height: 8),
            Row(children: [
              if ((a['loan_rate'] ?? 0) > 0) ...[
                const Icon(Icons.percent, color: PC.sage, size: 12),
                const SizedBox(width: 4),
                Text('${(double.tryParse(a['loan_rate'].toString()) ?? 0).toStringAsFixed(2)}% APR',
                    style: const TextStyle(color: PC.sage, fontSize: 11)),
                const SizedBox(width: 16),
              ],
              if ((a['loan_term_months'] ?? 0) > 0) ...[
                const Icon(Icons.schedule, color: PC.sage, size: 12),
                const SizedBox(width: 4),
                Builder(builder: (_) {
                  final months = (a['loan_term_months'] as num).toInt();
                  final years  = months ~/ 12;
                  final rem    = months % 12;
                  final label  = years > 0
                      ? (rem > 0 ? '$years yr $rem mo' : '$years yr')
                      : '$months mo';
                  return Text('$label term',
                      style: const TextStyle(color: PC.sage, fontSize: 11));
                }),
              ],
            ]),
          ],
          if ((a['loan_original_amount'] ?? 0) > 0) ...[
            const SizedBox(height: 10),
            Builder(builder: (_) {
              final orig = double.tryParse(a['loan_original_amount'].toString()) ?? 0;
              final progress = orig > 0 ? (1 - (current / orig)).clamp(0.0, 1.0) : 0.0;
              return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: progress,
                    backgroundColor: PC.surface,
                    valueColor: const AlwaysStoppedAnimation<Color>(PC.green),
                    minHeight: 6,
                  ),
                ),
                const SizedBox(height: 4),
                Row(children: [
                  Text('${(progress * 100).toStringAsFixed(0)}% paid off',
                      style: const TextStyle(color: PC.green, fontSize: 10)),
                  const Spacer(),
                  if ((a['loan_payment'] ?? 0) > 0) Builder(builder: (_) {
                    final payment = double.tryParse(a['loan_payment'].toString()) ?? 0;
                    if (payment <= 0 || current <= 0) return const SizedBox();
                    final months = (current / payment).ceil();
                    final payoff = DateTime(DateTime.now().year, DateTime.now().month + months);
                    return Text('Payoff ~${DateFormat('MMM yyyy').format(payoff)}',
                        style: const TextStyle(color: PC.sage, fontSize: 10));
                  }),
                ]),
              ]);
            }),
          ],
        ] else ...[
          Row(children: [
            Expanded(child: _balanceCol('CURRENT', _fmt.format(current), Colors.white)),
            Expanded(child: _balanceCol('AVAILABLE', _fmt.format(available), PC.green)),
          ]),
        ],
      ]),
    );
  }

  Widget _balanceCol(String label, String value, Color color) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 1)),
      const SizedBox(height: 4),
      Text(value, style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
    ],
  );

  IconData _accountIcon(String type, String subtype) {
    if (type == 'credit') return Icons.credit_card;
    if (type == 'loan')   return Icons.home;
    if (subtype == 'savings') return Icons.savings;
    return Icons.account_balance;
  }

  Widget _empty() => Center(child: Column(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      Icon(Icons.account_balance, size: 64, color: PC.pink.withOpacity(0.3)),
      const SizedBox(height: 16),
      const Text('No accounts connected',
          style: TextStyle(color: Colors.white, fontSize: 16)),
      const SizedBox(height: 8),
      const Text('Tap + to connect a bank',
          style: TextStyle(color: PC.sage, fontSize: 13)),
      const SizedBox(height: 24),
      ElevatedButton.icon(
        style: ElevatedButton.styleFrom(
            backgroundColor: PC.pink, foregroundColor: PC.background,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
        onPressed: _connectBank,
        icon: const Icon(Icons.add_card),
        label: const Text('Connect Bank',
            style: TextStyle(fontWeight: FontWeight.bold)),
      ),
    ],
  ));
}
