import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../services/api_service.dart';

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({super.key});
  @override
  State<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  final _fmt    = NumberFormat.currency(symbol: '\$');
  final _search = TextEditingController();
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  List<Map<String, dynamic>> _txns     = [];
  List<Map<String, dynamic>> _filtered = [];
  List<String> _customCategories = [];
  Map<String, String> _catOverrides  = {}; // txn_id → category
  Map<String, String> _merchantRules = {}; // merchant_name → category
  Set<String> _blockedNativeCats    = {}; // normalized Plaid cats blocked → Uncategorized
  Set<String> _hiddenTxnIds         = {}; // locally hidden transaction IDs
  List<Map<String, dynamic>> _accounts = [];
  bool _loading = true;
  String? _filterCat;
  String? _filterBank;

  static const _baseCategories = [
    'Food & Drink', 'Shopping', 'Travel', 'Entertainment',
    'Gas', 'Utilities', 'Healthcare', 'Subscription', 'Bill',
    'Income', 'Transfer', 'Other', 'Uncategorized',
  ];

  // Map Plaid SNAKE_CASE → human-readable
  static const _plaidLabels = {
    'FOOD_AND_DRINK':           'Food & Drink',
    'GENERAL_MERCHANDISE':      'Shopping',
    'RENT_AND_UTILITIES':       'Utilities',
    'PERSONAL_CARE':            'Personal Care',
    'TRANSFER_OUT':             'Transfer',
    'TRANSFER_IN':              'Income',
    'LOAN_PAYMENTS':            'Loan',
    'GENERAL_SERVICES':         'Services',
    'GOVERNMENT_AND_NON_PROFIT':'Government',
    'INCOME':                   'Income',
  };

  static String _normCat(String? raw) {
    if (raw == null || raw.isEmpty) return 'Other';
    if (_plaidLabels.containsKey(raw)) return _plaidLabels[raw]!;
    // Handle all-caps words/phrases (with or without underscores)
    if (raw == raw.toUpperCase()) {
      return raw.split('_').map((w) => w.isEmpty
          ? '' : w[0].toUpperCase() + w.substring(1).toLowerCase()).join(' ');
    }
    return raw;
  }

  List<String> get _allCategories => [
    ..._baseCategories,
    ..._customCategories.where((c) => !_baseCategories.contains(c)),
  ];

  // Build chips from effective categories so overrides/rules are reflected
  List<String> get _availableCategories {
    final cats = _txns
        .map((t) => _effectiveCat(t))
        .toSet()
        .toList();
    cats.sort();
    return cats;
  }

  @override
  void initState() {
    super.initState();
    _search.addListener(_filter);
    categoriesChanged.addListener(_onCategoriesChanged);
    _loadCustomCategories();
    _loadCatOverrides();
    _loadMerchantRules();
    _loadBlockedNativeCats();
    _loadHiddenTxns();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    categoriesChanged.removeListener(_onCategoriesChanged);
    super.dispose();
  }

  // Reload merchant rules when another screen (e.g. the AI assistant) edits them.
  void _onCategoriesChanged() => _loadMerchantRules();

  Future<void> _loadCustomCategories() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('custom_categories');
    if (raw != null && mounted) {
      setState(() => _customCategories = List<String>.from(jsonDecode(raw)));
    }
  }

  Future<void> _saveCustomCategories() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('custom_categories', jsonEncode(_customCategories));
  }

  Future<void> _loadCatOverrides() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('category_overrides');
    if (raw != null && mounted) {
      final map = Map<String, dynamic>.from(jsonDecode(raw));
      setState(() => _catOverrides = map.map((k, v) => MapEntry(k, v.toString())));
    }
  }

  Future<void> _saveCatOverride(String txnId, String category) async {
    final prefs = await SharedPreferences.getInstance();
    final updated = {..._catOverrides, txnId: category};
    await prefs.setString('category_overrides', jsonEncode(updated));
    if (mounted) setState(() => _catOverrides = updated);
  }

  Future<void> _loadMerchantRules() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('merchant_rules');
    if (raw != null && mounted) {
      final map = Map<String, dynamic>.from(jsonDecode(raw));
      setState(() => _merchantRules = map.map((k, v) => MapEntry(k, v.toString())));
    }
  }

  Future<void> _saveMerchantRule(String merchant, String category) async {
    final prefs = await SharedPreferences.getInstance();
    final updated = {..._merchantRules, merchant: category};
    await prefs.setString('merchant_rules', jsonEncode(updated));
    if (mounted) setState(() => _merchantRules = updated);
  }

  Future<void> _loadBlockedNativeCats() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('blocked_native_cats');
    if (raw != null && mounted) {
      setState(() => _blockedNativeCats = Set<String>.from(jsonDecode(raw)));
    }
  }

  Future<void> _loadHiddenTxns() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('hidden_txn_ids');
    if (raw != null && mounted) {
      setState(() => _hiddenTxnIds = Set<String>.from(jsonDecode(raw)));
    }
  }

  Future<void> _hideTxn(Map<String, dynamic> t) async {
    final id = t['transaction_id']?.toString() ?? t['id']?.toString() ?? '';
    if (id.isEmpty) return;
    final updated = {..._hiddenTxnIds, id};
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('hidden_txn_ids', jsonEncode(updated.toList()));
    if (mounted) setState(() => _hiddenTxnIds = updated);
    _filter();
  }

  Future<void> _unhideTxn(Map<String, dynamic> t) async {
    final id = t['transaction_id']?.toString() ?? t['id']?.toString() ?? '';
    final updated = Set<String>.from(_hiddenTxnIds)..remove(id);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('hidden_txn_ids', jsonEncode(updated.toList()));
    if (mounted) setState(() => _hiddenTxnIds = updated);
    _filter();
  }

  Future<void> _saveBlockedNativeCats() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('blocked_native_cats', jsonEncode(_blockedNativeCats.toList()));
  }

  String _effectiveCat(Map<String, dynamic> t) {
    // 1. Per-transaction override (just this one)
    final id = t['transaction_id']?.toString() ?? t['id']?.toString() ?? '';
    if (id.isNotEmpty && _catOverrides.containsKey(id)) return _catOverrides[id]!;
    // 2. Merchant-wide local rule (all transactions from this merchant)
    final merchant = (t['merchant_name'] ?? t['name'] ?? '').toString();
    if (merchant.isNotEmpty && _merchantRules.containsKey(merchant)) {
      return _merchantRules[merchant]!;
    }
    // 3. Backend category, normalized — blocked native cats fall through to Uncategorized
    final normalized = _normCat(t['category']?.toString());
    if (_blockedNativeCats.contains(normalized)) return 'Uncategorized';
    return normalized;
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final results = await Future.wait([
        ApiService.getTransactions(_month.month, _month.year),
        ApiService.getAccounts(),
      ]);
      if (mounted) setState(() {
        _txns     = results[0] as List<Map<String, dynamic>>;
        _accounts = results[1] as List<Map<String, dynamic>>;
        _filter();
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  // Unique institution names from loaded accounts (excludes manual)
  List<String> get _banks {
    final seen = <String>{};
    final banks = <String>[];
    for (final a in _accounts) {
      if (a['item_id'] == '__manual__' || a['source'] == 'manual') continue;
      final inst = (a['institution_name'] ?? '').toString();
      if (inst.isNotEmpty && seen.add(inst)) banks.add(inst);
    }
    return banks;
  }

  // Map account_name → institution_name for filtering
  String _institutionForTxn(Map<String, dynamic> t) {
    final accountName = (t['account_name'] ?? '').toString();
    for (final a in _accounts) {
      if ((a['name'] ?? '').toString() == accountName) {
        return (a['institution_name'] ?? '').toString();
      }
    }
    return accountName; // fallback: use account_name directly
  }

  void _filter() {
    final q    = _search.text.toLowerCase();
    final cat  = _filterCat;
    final bank = _filterBank;
    setState(() => _filtered = _txns.where((t) {
      final id = t['transaction_id']?.toString() ?? t['id']?.toString() ?? '';
      if (_hiddenTxnIds.contains(id)) return false;
      final matchQ = q.isEmpty ||
          (t['name']          ?? '').toString().toLowerCase().contains(q) ||
          (t['merchant_name'] ?? '').toString().toLowerCase().contains(q);
      final matchCat  = cat  == null || _effectiveCat(t) == cat;
      final matchBank = bank == null || _institutionForTxn(t) == bank;
      return matchQ && matchCat && matchBank;
    }).toList());
  }

  Future<void> _showTxnOptions(Map<String, dynamic> t) async {
    final amt  = double.tryParse(t['amount']?.toString() ?? '0') ?? 0;
    final name = (t['merchant_name'] ?? t['name'] ?? '').toString();
    final cat  = _effectiveCat(t);

    await showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(width: 40, height: 4,
                decoration: BoxDecoration(color: Colors.white24,
                    borderRadius: BorderRadius.circular(2))),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(children: [
                Expanded(child: Text(name,
                    style: const TextStyle(color: Colors.white, fontSize: 15,
                        fontWeight: FontWeight.bold),
                    overflow: TextOverflow.ellipsis)),
                Text(_fmt.format(amt.abs()),
                    style: const TextStyle(color: PC.gold, fontSize: 15,
                        fontWeight: FontWeight.bold)),
              ]),
            ),
            const SizedBox(height: 16),
            const Divider(color: Colors.white10, height: 1),
            ListTile(
              leading: const Icon(Icons.label_outline, color: PC.pink),
              title: const Text('Set Category',
                  style: TextStyle(color: Colors.white, fontSize: 14)),
              subtitle: Text(cat,
                  style: const TextStyle(color: PC.sage, fontSize: 11)),
              onTap: () { Navigator.pop(ctx); _setCategory(t); },
            ),
            ListTile(
              leading: const Icon(Icons.receipt_long, color: PC.gold),
              title: const Text('Add as Bill',
                  style: TextStyle(color: Colors.white, fontSize: 14)),
              subtitle: const Text('Create a recurring bill from this transaction',
                  style: TextStyle(color: PC.sage, fontSize: 11)),
              onTap: () { Navigator.pop(ctx); _addAsBill(name, amt.abs()); },
            ),
            ListTile(
              leading: const Icon(Icons.visibility_off_outlined, color: PC.sage),
              title: const Text('Hide Transaction',
                  style: TextStyle(color: Colors.white, fontSize: 14)),
              subtitle: const Text('Remove duplicate or erroneous transaction from view',
                  style: TextStyle(color: PC.sage, fontSize: 11)),
              onTap: () async {
                Navigator.pop(ctx);
                await _hideTxn(t);
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: const Text('Transaction hidden'),
                    backgroundColor: PC.card,
                    action: SnackBarAction(
                      label: 'Undo',
                      textColor: PC.pink,
                      onPressed: () => _unhideTxn(t),
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Future<void> _setCategory(Map<String, dynamic> t) async {
    final merchant = (t['merchant_name'] ?? t['name'] ?? '').toString();
    final currentCat = _normCat(t['category']?.toString());

    final chosen = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.55,
        maxChildSize: 0.85,
        minChildSize: 0.3,
        builder: (_, ctrl) => Column(
          children: [
            const SizedBox(height: 8),
            Container(width: 40, height: 4,
                decoration: BoxDecoration(color: Colors.white24,
                    borderRadius: BorderRadius.circular(2))),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(children: [
                const Expanded(child: Text('Set Category',
                    style: TextStyle(color: Colors.white, fontSize: 16,
                        fontWeight: FontWeight.bold))),
                GestureDetector(
                  onTap: () async {
                    Navigator.pop(ctx);
                    await _createCustomCategory();
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: PC.grove,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.add, color: PC.sage, size: 14),
                      SizedBox(width: 4),
                      Text('Custom', style: TextStyle(color: PC.sage, fontSize: 12)),
                    ]),
                  ),
                ),
              ]),
            ),
            const Divider(color: Colors.white10, height: 1),
            Expanded(
              child: ListView(
                controller: ctrl,
                children: [
                  ..._allCategories.map((c) => ListTile(
                    title: Text(c, style: const TextStyle(color: Colors.white)),
                    leading: Icon(
                        currentCat == c ? Icons.check_circle : Icons.radio_button_unchecked,
                        color: PC.pink),
                    onTap: () => Navigator.pop(ctx, c),
                  )),
                  const SizedBox(height: 16),
                ],
              ),
            ),
          ],
        ),
      ),
    );

    if (chosen == null || !mounted) return;

    // Ask scope: just this transaction, or all from this merchant
    final applyAll = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: PC.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Apply "$chosen" to...',
            style: const TextStyle(color: Colors.white, fontSize: 16)),
        content: Text(
          'Apply to just this transaction, or all future & past transactions from "$merchant"?',
          style: const TextStyle(color: PC.sage, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Just this one', style: TextStyle(color: PC.sage)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: PC.pink, foregroundColor: PC.background),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text('All "$merchant"',
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );

    if (applyAll == null || !mounted) return;

    if (applyAll) {
      await _saveMerchantRule(merchant, chosen); // local, primary
      ApiService.setMerchantCategory(merchant, chosen).catchError((_) {}); // fire-and-forget
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('All "$merchant" transactions → $chosen'),
        backgroundColor: PC.grove,
      ));
    } else {
      final txnId = t['transaction_id']?.toString() ?? t['id']?.toString() ?? '';
      if (txnId.isNotEmpty) {
        await _saveCatOverride(txnId, chosen);
      }
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('This transaction → $chosen'),
        backgroundColor: PC.grove,
      ));
    }
    _filter();
  }

  Future<void> _createCustomCategory() async {
    final ctrl = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: PC.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('New Category', style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: 'e.g. "Pet Care"',
            hintStyle: const TextStyle(color: PC.sage),
            filled: true, fillColor: PC.card,
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
            focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: PC.pink)),
          ),
          onSubmitted: (v) => Navigator.pop(ctx, v.trim()),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: PC.sage))),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: PC.pink, foregroundColor: PC.background),
            onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
            child: const Text('Add'),
          ),
        ],
      ),
    );
    if (result != null && result.isNotEmpty && !_allCategories.contains(result)) {
      setState(() => _customCategories = [..._customCategories, result]);
      await _saveCustomCategories();
    }
  }

  Future<void> _deleteCategoryChip(String category) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: PC.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Remove "$category"?',
            style: const TextStyle(color: Colors.white, fontSize: 15)),
        content: Text(
          'All transactions in "$category" will move to Uncategorized. '
          'You can recategorize them individually at any time.',
          style: const TextStyle(color: PC.sage, fontSize: 13),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel', style: TextStyle(color: PC.sage))),
          TextButton(onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete', style: TextStyle(color: PC.red))),
        ],
      ),
    );
    if (ok == true && mounted) {
      final prefs = await SharedPreferences.getInstance();
      // Remove from custom list
      if (_customCategories.contains(category)) {
        setState(() => _customCategories = _customCategories.where((c) => c != category).toList());
        await _saveCustomCategories();
      }
      // Clear overrides pointing to this category
      final clearedOverrides = Map<String, String>.from(_catOverrides)
        ..removeWhere((_, v) => v == category);
      await prefs.setString('category_overrides', jsonEncode(clearedOverrides));
      // Clear merchant rules pointing to this category
      final clearedRules = Map<String, String>.from(_merchantRules)
        ..removeWhere((_, v) => v == category);
      await prefs.setString('merchant_rules', jsonEncode(clearedRules));
      // Block the native Plaid category so those transactions fall through to Uncategorized
      final updatedBlocked = {..._blockedNativeCats, category};
      await prefs.setString('blocked_native_cats', jsonEncode(updatedBlocked.toList()));
      if (mounted) setState(() {
        _catOverrides     = clearedOverrides;
        _merchantRules    = clearedRules;
        _blockedNativeCats = updatedBlocked;
        if (_filterCat == category) _filterCat = null;
      });
      // Fire-and-forget backend cleanup
      ApiService.deleteMerchantCategoriesByCategory(category).catchError((_) {});
      _filter();
    }
  }

  Future<void> _addAsBill(String name, double amount) async {
    final nameCtrl = TextEditingController(text: name);
    final amtCtrl  = TextEditingController(text: amount.toStringAsFixed(2));
    final dueCtrl  = TextEditingController();
    String cat = 'Subscription';
    final cats = ['Bill', 'Subscription', 'Insurance', 'Utilities', 'Rent', 'Loan', 'Other'];

    await showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
            left: 20, right: 20, top: 20,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 20),
        child: StatefulBuilder(builder: (ctx, set) => Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Add as Bill',
                style: TextStyle(color: Colors.white, fontSize: 18,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 20),
            _field(nameCtrl, 'Name', TextInputType.text),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: _field(amtCtrl, 'Amount',
                  const TextInputType.numberWithOptions(decimal: true))),
              const SizedBox(width: 12),
              Expanded(child: _field(dueCtrl, 'Due day (1–31)',
                  TextInputType.number)),
            ]),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: cat,
              dropdownColor: PC.card,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                labelText: 'Category',
                labelStyle: const TextStyle(color: PC.sage),
                filled: true, fillColor: PC.card,
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide.none),
              ),
              items: cats.map((c) =>
                  DropdownMenuItem(value: c, child: Text(c))).toList(),
              onChanged: (v) => set(() => cat = v ?? cat),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity, height: 48,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                    backgroundColor: PC.pink,
                    foregroundColor: PC.background,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12))),
                onPressed: () async {
                  final n = nameCtrl.text.trim();
                  final a = double.tryParse(amtCtrl.text) ?? 0;
                  final d = int.tryParse(dueCtrl.text);
                  if (n.isEmpty) return;
                  Navigator.pop(ctx);
                  try {
                    await ApiService.createBill(
                        name: n, amount: a, dueDay: d, category: cat);
                    if (mounted) ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Bill added!'),
                          backgroundColor: PC.green));
                  } catch (e) {
                    if (mounted) ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Error: $e'),
                          backgroundColor: PC.red));
                  }
                },
                child: const Text('ADD BILL',
                    style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2)),
              ),
            ),
          ],
        )),
      ),
    );
  }

  Widget _field(TextEditingController ctrl, String label, TextInputType type) =>
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(title: const Text('TRANSACTIONS')),
      body: Column(children: [
        // Month picker
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            IconButton(
              icon: const Icon(Icons.chevron_left, color: PC.sage),
              onPressed: () {
                setState(() => _month = DateTime(_month.year, _month.month - 1));
                _load();
              },
            ),
            Text(DateFormat('MMMM yyyy').format(_month),
                style: const TextStyle(color: Colors.white, fontSize: 16,
                    fontWeight: FontWeight.bold)),
            IconButton(
              icon: const Icon(Icons.chevron_right, color: PC.sage),
              onPressed: _month.month == DateTime.now().month &&
                      _month.year == DateTime.now().year ? null : () {
                setState(() => _month = DateTime(_month.year, _month.month + 1));
                _load();
              },
            ),
          ]),
        ),

        // Search
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: TextField(
            controller: _search,
            style: const TextStyle(color: Colors.white, fontSize: 14),
            decoration: InputDecoration(
              hintText: 'Search transactions...',
              hintStyle: TextStyle(color: PC.sage.withOpacity(0.6)),
              prefixIcon: const Icon(Icons.search, color: PC.sage, size: 20),
              suffixIcon: _search.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear, color: PC.sage, size: 18),
                      onPressed: () { _search.clear(); _filter(); })
                  : null,
              filled: true, fillColor: PC.card,
              contentPadding: const EdgeInsets.symmetric(vertical: 12),
              border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
              focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: PC.pink, width: 1.5)),
            ),
          ),
        ),

        // Bank filter chips (only shown when >1 bank connected)
        if (_banks.length > 1) ...[
          SizedBox(
            height: 34,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                _bankChip('All Banks', _filterBank == null,
                    () => setState(() { _filterBank = null; _filter(); })),
                ..._banks.map((b) => _bankChip(b, _filterBank == b,
                    () => setState(() { _filterBank = _filterBank == b ? null : b; _filter(); }))),
              ],
            ),
          ),
          const SizedBox(height: 4),
        ],

        // Category filter chips
        SizedBox(
          height: 36,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            children: [
              _chip('All', _filterCat == null,
                  () => setState(() { _filterCat = null; _filter(); })),
              ..._availableCategories.map((c) => _chip(c, _filterCat == c,
                () => setState(() { _filterCat = _filterCat == c ? null : c; _filter(); }),
                onLongPress: () => _deleteCategoryChip(c),
              )),
              // "+" chip to create custom category
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: GestureDetector(
                  onTap: _createCustomCategory,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: PC.grove,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: PC.sage.withOpacity(0.3), width: 1.5),
                    ),
                    child: const Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.add, color: PC.sage, size: 12),
                      SizedBox(width: 2),
                      Text('New', style: TextStyle(color: PC.sage,
                          fontSize: 11, fontWeight: FontWeight.bold)),
                    ]),
                  ),
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(left: 16, top: 4, bottom: 4),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text('Long-press a category to delete its rules',
                style: TextStyle(color: PC.sage.withOpacity(0.5), fontSize: 9)),
          ),
        ),

        if (!_loading && _filtered.isNotEmpty) _summaryBar(),

        Expanded(child: _loading
            ? const Center(child: CircularProgressIndicator(color: PC.pink))
            : _filtered.isEmpty
                ? _empty()
                : RefreshIndicator(
                    color: PC.pink,
                    backgroundColor: PC.surface,
                    onRefresh: _load,
                    child: ListView.builder(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 40),
                      itemCount: _filtered.length,
                      itemBuilder: (_, i) => _txnCard(_filtered[i]),
                    ),
                  )),
      ]),
    );
  }

  Widget _summaryBar() {
    double spent = 0, income = 0;
    for (final t in _filtered) {
      final amt = double.tryParse(t['amount']?.toString() ?? '0') ?? 0;
      final cat = _effectiveCat(t);
      final isIncome = amt < 0 || cat.toLowerCase() == 'income';
      if (isIncome) income += amt.abs();
      else spent += amt;
    }
    final label = _filterCat != null ? _filterCat! : 'All';
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: Row(children: [
        Text('$label  ·  ${_filtered.length} transactions',
            style: const TextStyle(color: PC.sage, fontSize: 11)),
        const Spacer(),
        if (income > 0) ...[
          Text('+${_fmt.format(income)}',
              style: const TextStyle(color: PC.green, fontSize: 12, fontWeight: FontWeight.bold)),
          const SizedBox(width: 10),
        ],
        if (spent > 0)
          Text(_fmt.format(spent),
              style: const TextStyle(color: PC.pink, fontSize: 12, fontWeight: FontWeight.bold)),
      ]),
    );
  }

  Widget _bankChip(String label, bool selected, VoidCallback onTap) =>
      Padding(
        padding: const EdgeInsets.only(right: 8),
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
            decoration: BoxDecoration(
              color: selected ? PC.gold.withOpacity(0.15) : PC.card,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                  color: selected ? PC.gold : Colors.white10, width: 1.5),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.account_balance,
                  size: 10, color: selected ? PC.gold : PC.sage),
              const SizedBox(width: 4),
              Text(label,
                  style: TextStyle(
                      color: selected ? PC.gold : PC.sage,
                      fontSize: 11, fontWeight: FontWeight.bold)),
            ]),
          ),
        ),
      );

  Widget _chip(String label, bool selected, VoidCallback onTap,
      {VoidCallback? onLongPress}) =>
      Padding(
        padding: const EdgeInsets.only(right: 8),
        child: GestureDetector(
          onTap: onTap,
          onLongPress: onLongPress,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: selected ? PC.pink.withOpacity(0.2) : PC.card,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                  color: selected ? PC.pink : Colors.white10, width: 1.5),
            ),
            child: Text(label,
                style: TextStyle(
                    color: selected ? PC.pink : PC.sage,
                    fontSize: 11, fontWeight: FontWeight.bold)),
          ),
        ),
      );

  Widget _txnCard(Map<String, dynamic> t) {
    final amt      = double.tryParse(t['amount']?.toString() ?? '0') ?? 0;
    final cat      = _effectiveCat(t);
    final isIncome = amt < 0 || cat.toLowerCase() == 'income';
    final name     = t['merchant_name'] ?? t['name'] ?? '';
    final rawDate  = t['date']?.toString() ?? '';
    // Format date nicely if it's a full ISO timestamp
    String date = rawDate;
    try {
      final parsed = DateTime.parse(rawDate);
      date = DateFormat('MMM d').format(parsed);
    } catch (_) {}

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: PC.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        leading: Container(
          width: 40, height: 40,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isIncome ? PC.green.withOpacity(0.15) : PC.pink.withOpacity(0.12),
          ),
          child: Icon(
            isIncome ? Icons.arrow_downward : Icons.arrow_upward,
            color: isIncome ? PC.green : PC.pink,
            size: 18,
          ),
        ),
        title: Text(name.toString(),
            style: const TextStyle(color: Colors.white, fontSize: 13),
            maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Row(children: [
            _catBadge(cat),
            const SizedBox(width: 8),
            Text(date, style: const TextStyle(color: PC.sage, fontSize: 10)),
            const SizedBox(width: 4),
            Expanded(child: Text('· ${t['account_name'] ?? ''}',
                style: const TextStyle(color: PC.sage, fontSize: 10),
                overflow: TextOverflow.ellipsis)),
          ]),
        ),
        trailing: Text(
          isIncome ? '+${_fmt.format(amt.abs())}' : _fmt.format(amt.abs()),
          style: TextStyle(
              color: isIncome ? PC.green : Colors.white,
              fontSize: 14, fontWeight: FontWeight.bold),
        ),
        onTap: () => _showTxnOptions(t),
      ),
    );
  }

  Widget _catBadge(String label) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    decoration: BoxDecoration(
      color: PC.grove.withOpacity(0.4),
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(label,
        style: const TextStyle(color: PC.sage, fontSize: 9, letterSpacing: 1)),
  );

  Widget _empty() => Center(child: Column(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      Icon(Icons.receipt, size: 64, color: PC.pink.withOpacity(0.3)),
      const SizedBox(height: 16),
      Text(
        _search.text.isEmpty && _filterCat == null
            ? 'No transactions this month'
            : 'No results found',
        style: const TextStyle(color: PC.sage, fontSize: 16),
      ),
    ],
  ));
}
