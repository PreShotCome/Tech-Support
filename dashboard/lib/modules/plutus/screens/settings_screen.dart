import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../services/ai_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlCtrl = TextEditingController();
  final _aiKeyCtrl = TextEditingController();
  bool _loading  = true;
  bool _healthy  = false;
  bool _syncing  = false;
  String? _syncResult;

  @override
  void initState() { super.initState(); _load(); }

  @override
  void dispose() { _urlCtrl.dispose(); _aiKeyCtrl.dispose(); super.dispose(); }

  Future<void> _load() async {
    await ApiService.loadBaseUrl();
    await AiService.loadKey();
    final ok = await ApiService.checkHealth();
    if (mounted) setState(() {
      _urlCtrl.text = ApiService.baseUrl;
      _healthy = ok;
      _loading = false;
    });
  }

  Future<void> _saveAiKey() async {
    await AiService.setKey(_aiKeyCtrl.text);
    _aiKeyCtrl.clear();
    if (mounted) {
      setState(() {});
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('AI assistant key saved'),
        backgroundColor: PC.green,
      ));
    }
  }

  Future<void> _removeAiKey() async {
    await AiService.setKey('');
    if (mounted) setState(() {});
  }

  Future<void> _saveUrl() async {
    await ApiService.setBaseUrl(_urlCtrl.text.trim());
    final ok = await ApiService.checkHealth();
    setState(() => _healthy = ok);
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(ok ? 'Connected' : 'Cannot reach backend'),
      backgroundColor: ok ? PC.green : PC.red,
    ));
  }

  Future<void> _confirmSignOut() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: PC.surface,
        title: const Text('Sign out?', style: TextStyle(color: Colors.white)),
        content: const Text('You can sign back in any time.',
            style: TextStyle(color: PC.sage)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: PC.sage)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Sign Out', style: TextStyle(color: PC.red)),
          ),
        ],
      ),
    );
    if (yes == true) await AuthService.signOut();
  }

  Future<void> _runSync({bool full = false}) async {
    setState(() { _syncing = true; _syncResult = null; });
    try {
      final result = await ApiService.sync(full: full, days: full ? 730 : 90);
      final added = result['added'] ?? result['transactions_added'] ?? result['count'];
      if (mounted) setState(() {
        _syncResult = full
            ? 'Full sync complete${added != null ? ' · $added transactions fetched' : ''}'
            : 'Sync complete${added != null ? ' · $added new transactions' : ''}';
        _syncing = false;
      });
    } catch (e) {
      if (mounted) setState(() {
        _syncResult = 'Sync failed: $e';
        _syncing = false;
      });
    }
  }

  Future<void> _showCategoryRules() async {
    // Load from local SharedPreferences (source of truth)
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('merchant_rules');
    final Map<String, String> rulesMap = raw != null
        ? Map<String, dynamic>.from(jsonDecode(raw)).map((k, v) => MapEntry(k, v.toString()))
        : {};
    // Convert to list for display
    final List<Map<String, String>> rules =
        rulesMap.entries.map((e) => {'merchant': e.key, 'category': e.value}).toList();

    if (!mounted) return;

    await showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(builder: (ctx, set) {
        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.65,
          maxChildSize: 0.92,
          builder: (_, ctrl) => SafeArea(
            top: false,
            child: Column(
            children: [
              const SizedBox(height: 8),
              Container(width: 40, height: 4,
                  decoration: BoxDecoration(color: Colors.white24,
                      borderRadius: BorderRadius.circular(2))),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
                child: Row(children: [
                  const Icon(Icons.label_outline, color: PC.pink, size: 18),
                  const SizedBox(width: 8),
                  const Expanded(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Category Rules',
                          style: TextStyle(color: Colors.white, fontSize: 16,
                              fontWeight: FontWeight.bold)),
                      Text('Tap the trash icon to delete a rule and reset that merchant\'s category.',
                          style: TextStyle(color: PC.sage, fontSize: 11)),
                    ],
                  )),
                  IconButton(
                    icon: const Icon(Icons.close, color: PC.sage),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ]),
              ),
              const Divider(color: Colors.white10, height: 1),
              Expanded(
                child: rules.isEmpty
                    ? const Center(child: Padding(
                        padding: EdgeInsets.all(32),
                        child: Text('No category rules set yet.\nCategorize a transaction to create one.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: PC.sage, fontSize: 13))))
                    : ListView.builder(
                        controller: ctrl,
                        itemCount: rules.length,
                        itemBuilder: (_, i) {
                          final merchant = rules[i]['merchant'] ?? '';
                          final cat      = rules[i]['category'] ?? '';
                          return ListTile(
                            title: Text(merchant,
                                style: const TextStyle(color: Colors.white, fontSize: 13),
                                overflow: TextOverflow.ellipsis),
                            trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: PC.pink.withOpacity(0.12),
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(color: PC.pink.withOpacity(0.3)),
                                ),
                                child: Text(cat,
                                    style: const TextStyle(color: PC.pink, fontSize: 11)),
                              ),
                              IconButton(
                                icon: const Icon(Icons.delete_outline, color: PC.red, size: 20),
                                onPressed: () async {
                                  // Remove from local SharedPreferences
                                  final p = await SharedPreferences.getInstance();
                                  final currentRaw = p.getString('merchant_rules');
                                  final currentMap = currentRaw != null
                                      ? Map<String, dynamic>.from(jsonDecode(currentRaw))
                                      : <String, dynamic>{};
                                  currentMap.remove(merchant);
                                  await p.setString('merchant_rules', jsonEncode(currentMap));
                                  // Fire-and-forget backend cleanup
                                  ApiService.deleteMerchantCategory(merchant).catchError((_) {});
                                  set(() => rules.removeAt(i));
                                },
                              ),
                            ]),
                          );
                        },
                      ),
              ),
            ],
          ),
          ),
        );
      }),
    );
  }

  Future<void> _showNavCustomizer() async {
    // Import nav defs from main
    const allDefs = [
      (id: 'dashboard',    label: 'Overview',      icon: Icons.dashboard_outlined,       selIcon: Icons.dashboard),
      (id: 'safetospend',  label: 'Spendable',      icon: Icons.account_balance_wallet_outlined, selIcon: Icons.account_balance_wallet),
      (id: 'assistant',    label: 'Assistant',      icon: Icons.auto_awesome_outlined,    selIcon: Icons.auto_awesome),
      (id: 'transactions', label: 'Transactions',   icon: Icons.list_alt_outlined,        selIcon: Icons.list_alt),
      (id: 'bills',        label: 'Bills',          icon: Icons.receipt_long_outlined,    selIcon: Icons.receipt_long),
      (id: 'paycheck',     label: 'Paycheck',       icon: Icons.payments_outlined,        selIcon: Icons.payments),
      (id: 'accounts',     label: 'Accounts',       icon: Icons.account_balance_outlined, selIcon: Icons.account_balance),
      (id: 'calendar',     label: 'Calendar',       icon: Icons.calendar_month_outlined,  selIcon: Icons.calendar_month),
      (id: 'settings',     label: 'Settings',       icon: Icons.settings_outlined,        selIcon: Icons.settings),
    ];

    final p = await SharedPreferences.getInstance();
    final raw = p.getString('primary_tab_ids');
    List<String> draft = raw != null
        ? List<String>.from(jsonDecode(raw))
        : ['safetospend', 'bills', 'accounts'];

    if (!mounted) return;

    await showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(builder: (ctx, set) {
        return SafeArea(
          top: false,
          child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Customize Navigation',
                  style: TextStyle(color: Colors.white, fontSize: 18,
                      fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              const Text('Choose 3 tabs to show beside Dashboard.',
                  style: TextStyle(color: PC.sage, fontSize: 12)),
              const SizedBox(height: 16),
              ...allDefs.where((d) => d.id != 'dashboard').map((def) {
                final isSelected = draft.contains(def.id);
                final selIdx = draft.indexOf(def.id);
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Container(
                    width: 40, height: 40,
                    decoration: BoxDecoration(
                      color: isSelected ? PC.pink.withOpacity(0.12) : PC.card,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(isSelected ? def.selIcon : def.icon,
                        color: isSelected ? PC.pink : PC.sage, size: 20),
                  ),
                  title: Text(def.label,
                      style: TextStyle(
                          color: isSelected ? Colors.white : PC.sage,
                          fontSize: 14)),
                  trailing: isSelected
                      ? Container(
                          width: 24, height: 24,
                          decoration: const BoxDecoration(
                            color: PC.pink, shape: BoxShape.circle),
                          child: Center(child: Text('${selIdx + 1}',
                              style: const TextStyle(color: Colors.black,
                                  fontSize: 12, fontWeight: FontWeight.bold))),
                        )
                      : const Icon(Icons.add, color: PC.sage, size: 20),
                  onTap: () {
                    if (isSelected) {
                      set(() => draft.remove(def.id));
                    } else if (draft.length < 3) {
                      set(() => draft.add(def.id));
                    } else {
                      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                        content: Text('Remove one tab first to add another.'),
                        backgroundColor: PC.card,
                      ));
                    }
                  },
                );
              }),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity, height: 48,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: draft.length == 3 ? PC.pink : PC.grove,
                    foregroundColor: PC.background,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  onPressed: draft.length == 3 ? () async {
                    await p.setString('primary_tab_ids', jsonEncode(draft));
                    if (ctx.mounted) Navigator.pop(ctx);
                    if (mounted) ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Navigation updated.'),
                        backgroundColor: PC.card,
                      ));
                  } : null,
                  child: Text(
                    draft.length == 3 ? 'SAVE' : 'SELECT ${3 - draft.length} MORE',
                    style: const TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2),
                  ),
                ),
              ),
            ],
          ),
          ),
        );
      }),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(title: const Text('SETTINGS')),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: PC.pink))
          : ListView(padding: const EdgeInsets.all(20), children: [

              _section('BACKEND'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text(
                  'Enter your Railway backend URL. The app connects here to fetch your bank data.',
                  style: TextStyle(color: PC.sage, fontSize: 12, height: 1.5),
                ),
                const SizedBox(height: 12),
                Row(children: [
                  Container(width: 8, height: 8,
                      decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: _healthy ? PC.green : PC.red)),
                  const SizedBox(width: 8),
                  Text(_healthy ? 'Connected' : 'Not reachable',
                      style: TextStyle(
                          color: _healthy ? PC.green : PC.red, fontSize: 12)),
                ]),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: TextField(
                    controller: _urlCtrl,
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                    decoration: InputDecoration(
                      hintText: 'https://your-app.up.railway.app',
                      hintStyle: const TextStyle(color: PC.sage),
                      filled: true,
                      fillColor: PC.surface,
                      contentPadding:
                          const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: BorderSide.none),
                      focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: PC.pink)),
                    ),
                  )),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: PC.pink,
                      foregroundColor: PC.background,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: _saveUrl,
                    child: const Text('SAVE',
                        style: TextStyle(
                            fontSize: 11, fontWeight: FontWeight.bold)),
                  ),
                ]),
              ])),
              const SizedBox(height: 24),

              _section('ACCOUNT'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  const Icon(Icons.person_outline, color: PC.pink, size: 18),
                  const SizedBox(width: 10),
                  Expanded(child: Text(
                    AuthService.currentUser?.email ?? 'Signed in',
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                    overflow: TextOverflow.ellipsis,
                  )),
                ]),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: PC.red,
                      side: BorderSide(color: PC.red.withOpacity(0.5)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: _confirmSignOut,
                    icon: const Icon(Icons.logout, size: 16),
                    label: const Text('Sign Out', style: TextStyle(fontSize: 13)),
                  ),
                ),
              ])),
              const SizedBox(height: 24),

              _section('AI ASSISTANT'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(
                  AiService.hasKey
                      ? 'Your Anthropic API key is set (${AiService.keyPreview}). '
                          'The AI Assistant calls Claude directly from this device.'
                      : 'Add your own Anthropic API key to unlock the AI '
                          'Assistant. The key stays on this device and is sent '
                          'only to Anthropic — never to Plutus.',
                  style: const TextStyle(color: PC.sage, fontSize: 12, height: 1.5),
                ),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: TextField(
                    controller: _aiKeyCtrl,
                    obscureText: true,
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                    decoration: InputDecoration(
                      hintText: AiService.hasKey
                          ? 'Enter a new key to replace'
                          : 'sk-ant-...',
                      hintStyle: const TextStyle(color: PC.sage),
                      filled: true,
                      fillColor: PC.surface,
                      contentPadding:
                          const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: BorderSide.none),
                      focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: PC.pink)),
                    ),
                  )),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: PC.pink,
                      foregroundColor: PC.background,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: _saveAiKey,
                    child: const Text('SAVE',
                        style: TextStyle(
                            fontSize: 11, fontWeight: FontWeight.bold)),
                  ),
                ]),
                if (AiService.hasKey)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton(
                      onPressed: _removeAiKey,
                      child: const Text('Remove key',
                          style: TextStyle(color: PC.red, fontSize: 12)),
                    ),
                  ),
              ])),
              const SizedBox(height: 24),

              _section('TRANSACTIONS SYNC'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text(
                  'Sync pulls the latest transactions from Plaid. Use Full Sync if you are missing older transactions (fetches up to 2 years).',
                  style: TextStyle(color: PC.sage, fontSize: 12, height: 1.5),
                ),
                if (_syncResult != null) ...[
                  const SizedBox(height: 10),
                  Text(_syncResult!,
                      style: TextStyle(
                          color: _syncResult!.startsWith('Sync failed') ? PC.red : PC.green,
                          fontSize: 12)),
                ],
                const SizedBox(height: 14),
                Row(children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: PC.sage,
                        side: const BorderSide(color: PC.grove),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                      ),
                      onPressed: _syncing ? null : () => _runSync(),
                      icon: _syncing
                          ? const SizedBox(width: 14, height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2, color: PC.sage))
                          : const Icon(Icons.sync, size: 16),
                      label: const Text('Quick Sync', style: TextStyle(fontSize: 12)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: PC.gold,
                        foregroundColor: PC.background,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                      ),
                      onPressed: _syncing ? null : () => _runSync(full: true),
                      icon: _syncing
                          ? const SizedBox(width: 14, height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2, color: PC.background))
                          : const Icon(Icons.cloud_sync, size: 16),
                      label: const Text('Full Sync', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ]),
              ])),
              const SizedBox(height: 24),

              _section('CATEGORIES'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text(
                  'View and delete merchant category rules. Deleting a rule resets those transactions to their default category.',
                  style: TextStyle(color: PC.sage, fontSize: 12, height: 1.5),
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: PC.pink,
                      side: BorderSide(color: PC.pink.withOpacity(0.5)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: _showCategoryRules,
                    icon: const Icon(Icons.label_outline, size: 16),
                    label: const Text('Manage Category Rules',
                        style: TextStyle(fontSize: 13)),
                  ),
                ),
              ])),
              const SizedBox(height: 24),

              _section('NAVIGATION'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text(
                  'Choose which 3 tabs appear in the bottom nav bar. All others are in the More menu.',
                  style: TextStyle(color: PC.sage, fontSize: 12, height: 1.5),
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: PC.gold,
                      side: BorderSide(color: PC.gold.withOpacity(0.5)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: _showNavCustomizer,
                    icon: const Icon(Icons.tune, size: 16),
                    label: const Text('Customize Navigation',
                        style: TextStyle(fontSize: 13)),
                  ),
                ),
              ])),
              const SizedBox(height: 24),

              _section('ABOUT'),
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Plutus',
                    style: TextStyle(color: Colors.white, fontSize: 16,
                        fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                const Text('Grow wealth. Stay grounded.',
                    style: TextStyle(color: PC.sage, fontSize: 12)),
                const SizedBox(height: 12),
                const Divider(color: Colors.white10),
                const SizedBox(height: 12),
                const Text('Bank data powered by Plaid.',
                    style: TextStyle(color: PC.sage, fontSize: 11)),
              ])),
              const SizedBox(height: 32),
            ]),
    );
  }

  Widget _section(String t) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Text(t, style: const TextStyle(
        color: PC.sage, fontSize: 11,
        letterSpacing: 3, fontWeight: FontWeight.bold)),
  );

  Widget _card(Widget child) => Container(
    margin: const EdgeInsets.only(bottom: 4),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: PC.card,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: Colors.white.withOpacity(0.06)),
    ),
    child: child,
  );
}
