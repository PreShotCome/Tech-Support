import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart';
import '../services/ai_service.dart';
import '../services/api_service.dart';

/// AI assistant — chat about your finances, generate insights, find
/// subscriptions and categorize transactions. Powered by the user's own
/// Anthropic API key (BYOK); locked until a key is provided.
class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key});

  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> {
  final _inputCtrl = TextEditingController();
  final _keyCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();

  bool _keyReady = false;
  bool _savingKey = false;
  bool _keyObscure = true;

  String? _context;
  bool _contextLoading = false;
  List<Map<String, dynamic>> _txns = [];

  final List<_Msg> _messages = [];
  bool _sending = false;
  bool _categorizing = false;

  @override
  void initState() {
    super.initState();
    _init();
  }

  @override
  void dispose() {
    _inputCtrl.dispose();
    _keyCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _init() async {
    await AiService.loadKey();
    if (mounted) setState(() => _keyReady = true);
    if (AiService.hasKey) _loadContext();
  }

  // ── Financial context ──────────────────────────────────────────────────────

  Future<void> _loadContext() async {
    setState(() => _contextLoading = true);
    try {
      final now = DateTime.now();
      final prev = DateTime(now.year, now.month - 1);
      final results = await Future.wait([
        ApiService.getAccounts(),
        ApiService.getTransactions(now.month, now.year),
        ApiService.getTransactions(prev.month, prev.year),
        ApiService.getBills(now.month, now.year),
      ]);
      Map<String, dynamic> insights = {};
      try {
        insights = await ApiService.getIncomeInsights();
      } catch (_) {}
      List<Map<String, dynamic>> recurring = [];
      try {
        recurring = await ApiService.getRecurring();
      } catch (_) {}
      _txns = [...results[1], ...results[2]];
      _context = _formatContext(
        results[0],
        _txns,
        results[3],
        insights,
        recurring,
      );
    } catch (_) {
      _context = null;
    }
    if (mounted) setState(() => _contextLoading = false);
  }

  String _formatContext(
    List<Map<String, dynamic>> accounts,
    List<Map<String, dynamic>> txns,
    List<Map<String, dynamic>> bills,
    Map<String, dynamic> insights,
    List<Map<String, dynamic>> recurring,
  ) {
    final fmt = NumberFormat.currency(symbol: '\$');
    double d(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;
    final b = StringBuffer();

    b.writeln('ACCOUNTS:');
    for (final a in accounts) {
      final cur = d(a['current_balance']);
      final avail = double.tryParse(a['available_balance']?.toString() ?? '');
      b.writeln('- ${a['name']} (${a['type']}): '
          '${fmt.format(avail ?? cur)} available');
    }

    txns.sort((x, y) => '${y['date']}'.compareTo('${x['date']}'));
    b.writeln('\nRECENT TRANSACTIONS (newest first, - = spent, + = received):');
    for (final t in txns.take(50)) {
      final amt = d(t['amount']);
      final sign = amt > 0 ? '-' : '+';
      final label = (t['merchant_name'] ?? t['name'] ?? '').toString();
      b.writeln('${t['date']}  $label  $sign${fmt.format(amt.abs())}  '
          '${t['category'] ?? ''}');
    }

    if (bills.isNotEmpty) {
      b.writeln('\nBILLS:');
      for (final bill in bills) {
        b.writeln('- ${bill['name']}  ${fmt.format(d(bill['amount']))}  '
            'due day ${bill['due_day'] ?? '?'}');
      }
    }

    if (insights['deposit_count'] != null) {
      b.writeln('\nINCOME PATTERN:');
      b.writeln('- earned last 30 days: ${fmt.format(d(insights['income_30d']))}');
      b.writeln('- average deposit: ${fmt.format(d(insights['avg_deposit']))}');
      if (insights['projected_next_date'] != null) {
        b.writeln('- next deposit projected: ${insights['projected_next_date']}');
      }
    }

    if (recurring.isNotEmpty) {
      b.writeln('\nRECURRING CHARGES:');
      for (final r in recurring.take(20)) {
        b.writeln('- ${r['merchant']}  ~${fmt.format(d(r['avg_amount']))}  '
            'seen ${r['month_count']} months');
      }
    }
    return b.toString();
  }

  String _systemPrompt() {
    final data = _context ?? 'Financial data is currently unavailable.';
    return 'You are the financial assistant inside Plutus, a personal '
        'finance app. You are talking to the app\'s user. Use the real '
        'financial data below to answer. Be concise, specific and practical '
        '— reference actual numbers, merchants and dates, and avoid generic '
        'advice. If the data does not contain the answer, say so plainly. '
        'Format replies with short paragraphs or bullet points.\n\n'
        '=== USER FINANCIAL DATA ===\n$data';
  }

  // ── Sending ────────────────────────────────────────────────────────────────

  Future<void> _send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || _sending) return;
    setState(() {
      _messages.add(_Msg('user', trimmed));
      _sending = true;
    });
    _inputCtrl.clear();
    _scrollToBottom();
    try {
      final apiMessages = _messages
          .map((m) => {'role': m.role, 'content': m.text})
          .toList();
      final reply = await AiService.chat(
        system: _systemPrompt(),
        messages: apiMessages,
        maxTokens: 1200,
      );
      if (mounted) setState(() => _messages.add(_Msg('assistant', reply)));
    } catch (e) {
      if (mounted) {
        setState(() => _messages.add(_Msg(
            'assistant',
            'Something went wrong: '
                '${e.toString().replaceAll('Exception: ', '')}')));
      }
    } finally {
      if (mounted) setState(() => _sending = false);
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent + 120,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _saveKey() async {
    setState(() => _savingKey = true);
    await AiService.setKey(_keyCtrl.text);
    _keyCtrl.clear();
    if (mounted) setState(() => _savingKey = false);
    if (AiService.hasKey) {
      _loadContext();
      if (mounted) setState(() {});
    }
  }

  // ── UI ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      appBar: AppBar(
        title: const Text('ASSISTANT'),
        actions: [
          if (AiService.hasKey)
            IconButton(
              icon: _contextLoading
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: PC.pink))
                  : const Icon(Icons.refresh),
              tooltip: 'Refresh financial data',
              onPressed: _contextLoading ? null : _loadContext,
            ),
        ],
      ),
      body: !_keyReady
          ? const Center(child: CircularProgressIndicator(color: PC.pink))
          : !AiService.hasKey
              ? _setupView()
              : _chatView(),
    );
  }

  // ── Setup (no key) ─────────────────────────────────────────────────────────

  Widget _setupView() {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const SizedBox(height: 20),
        Center(
          child: Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: PC.pink.withOpacity(0.12),
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Icon(Icons.auto_awesome, color: PC.pink, size: 30),
          ),
        ),
        const SizedBox(height: 20),
        const Text('AI Assistant',
            textAlign: TextAlign.center,
            style: TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.bold)),
        const SizedBox(height: 10),
        const Text(
          'Chat about your money, get spending insights, find forgotten '
          'subscriptions and clean up categories — powered by Claude.\n\n'
          'This feature uses your own Anthropic API key. The key is stored '
          'only on this device and sent straight to Anthropic; Plutus never '
          'sees it. You pay Anthropic directly for what you use.',
          textAlign: TextAlign.center,
          style: TextStyle(color: PC.sage, fontSize: 13, height: 1.6),
        ),
        const SizedBox(height: 20),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: PC.card,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.white.withOpacity(0.06)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('ANTHROPIC API KEY',
                  style: TextStyle(
                      color: PC.sage,
                      fontSize: 10,
                      letterSpacing: 2,
                      fontWeight: FontWeight.bold)),
              const SizedBox(height: 10),
              TextField(
                controller: _keyCtrl,
                obscureText: _keyObscure,
                style: const TextStyle(color: Colors.white, fontSize: 13),
                decoration: InputDecoration(
                  hintText: 'sk-ant-...',
                  hintStyle: const TextStyle(color: PC.sage),
                  filled: true,
                  fillColor: PC.surface,
                  suffixIcon: IconButton(
                    icon: Icon(
                        _keyObscure
                            ? Icons.visibility
                            : Icons.visibility_off,
                        color: PC.sage,
                        size: 18),
                    onPressed: () =>
                        setState(() => _keyObscure = !_keyObscure),
                  ),
                  border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none),
                  focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: const BorderSide(color: PC.pink)),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                height: 46,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: PC.pink,
                    foregroundColor: PC.background,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: _savingKey ? null : _saveKey,
                  child: _savingKey
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: PC.background))
                      : const Text('SAVE KEY',
                          style: TextStyle(
                              fontWeight: FontWeight.bold, letterSpacing: 2)),
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'Create a key at console.anthropic.com → API Keys.',
                style: TextStyle(color: PC.sage, fontSize: 11),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ── Chat ───────────────────────────────────────────────────────────────────

  Widget _chatView() {
    return Column(
      children: [
        Expanded(
          child: _messages.isEmpty
              ? _welcome()
              : ListView.builder(
                  controller: _scrollCtrl,
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                  itemCount: _messages.length +
                      ((_sending || _categorizing) ? 1 : 0),
                  itemBuilder: (_, i) {
                    if (i >= _messages.length) return _thinkingBubble();
                    return _bubble(_messages[i]);
                  },
                ),
        ),
        _quickActions(),
        _inputBar(),
      ],
    );
  }

  Widget _welcome() {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 24),
        const Icon(Icons.auto_awesome, color: PC.pink, size: 32),
        const SizedBox(height: 14),
        const Text('Ask me anything about your money',
            textAlign: TextAlign.center,
            style: TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Text(
          _contextLoading
              ? 'Loading your financial data…'
              : _context == null
                  ? 'Heads up: your financial data could not be loaded, so '
                      'answers will be limited. Pull to refresh.'
                  : 'I can see your accounts, transactions, bills and income. '
                      'Try a question below or tap a shortcut.',
          textAlign: TextAlign.center,
          style: const TextStyle(color: PC.sage, fontSize: 13, height: 1.5),
        ),
        const SizedBox(height: 20),
        ...[
          'Where did most of my money go this month?',
          'Can I afford a \$200 purchase right now?',
          'What can I cut back on?',
        ].map((q) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: GestureDetector(
                onTap: () => _send(q),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    color: PC.card,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white.withOpacity(0.06)),
                  ),
                  child: Row(children: [
                    const Icon(Icons.chat_bubble_outline,
                        color: PC.sage, size: 15),
                    const SizedBox(width: 10),
                    Expanded(
                        child: Text(q,
                            style: const TextStyle(
                                color: Colors.white, fontSize: 13))),
                  ]),
                ),
              ),
            )),
      ],
    );
  }

  Widget _bubble(_Msg m) {
    final isUser = m.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.82),
        decoration: BoxDecoration(
          color: isUser ? PC.pink.withOpacity(0.16) : PC.card,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
              color: isUser
                  ? PC.pink.withOpacity(0.3)
                  : Colors.white.withOpacity(0.06)),
        ),
        child: SelectableText(
          m.text,
          style: TextStyle(
              color: isUser ? Colors.white : Colors.white.withOpacity(0.92),
              fontSize: 13,
              height: 1.45),
        ),
      ),
    );
  }

  Widget _thinkingBubble() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: PC.card,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white.withOpacity(0.06)),
        ),
        child: const SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(strokeWidth: 2, color: PC.pink),
        ),
      ),
    );
  }

  Widget _quickActions() {
    final busy = _sending || _categorizing;
    Widget chip(String label, IconData icon, VoidCallback onTap) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: ActionChip(
            backgroundColor: PC.card,
            side: BorderSide(color: PC.pink.withOpacity(0.3)),
            avatar: Icon(icon, color: PC.pink, size: 15),
            label: Text(label,
                style: const TextStyle(color: Colors.white, fontSize: 12)),
            onPressed: busy ? null : onTap,
          ),
        );
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        children: [
          chip('Insights', Icons.insights_outlined, () => _send(
              'Analyse my spending over the last two months. Call out my '
              'biggest categories, anything unusual, and 2-3 concrete things '
              'I could do. Keep it short.')),
          chip('Subscriptions', Icons.subscriptions_outlined, () => _send(
              'From my recurring charges and transactions, list my likely '
              'subscriptions and memberships. Flag any that look easy to '
              'forget, with the monthly cost and yearly total.')),
          chip('Categorize', Icons.label_outline, _runCategorize),
        ],
      ),
    );
  }

  // ── Categorization ─────────────────────────────────────────────────────────

  // Mirrors the base categories in transactions_screen.dart.
  static const _baseCategories = [
    'Food & Drink', 'Shopping', 'Travel', 'Entertainment', 'Gas',
    'Utilities', 'Healthcare', 'Subscription', 'Bill', 'Income',
    'Transfer', 'Other',
  ];

  Future<List<String>> _categoryList() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('custom_categories');
    final custom = raw != null ? List<String>.from(jsonDecode(raw)) : <String>[];
    return [
      ..._baseCategories,
      ...custom.where((c) => !_baseCategories.contains(c)),
    ];
  }

  String _prettyCat(String? raw) {
    if (raw == null || raw.isEmpty) return 'Uncategorized';
    if (raw == raw.toUpperCase()) {
      return raw
          .split('_')
          .map((w) => w.isEmpty ? '' : w[0] + w.substring(1).toLowerCase())
          .join(' ');
    }
    return raw;
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg), backgroundColor: PC.card));
  }

  Future<void> _runCategorize() async {
    if (_sending || _categorizing) return;
    if (_txns.isEmpty) {
      _snack('No transactions loaded yet — tap refresh and try again.');
      return;
    }
    setState(() {
      _messages.add(_Msg('user', 'Categorize my recent transactions'));
      _categorizing = true;
    });
    _scrollToBottom();
    try {
      final prefs = await SharedPreferences.getInstance();
      final rulesRaw = prefs.getString('merchant_rules');
      final rules = rulesRaw != null
          ? Map<String, dynamic>.from(jsonDecode(rulesRaw))
              .map((k, v) => MapEntry(k, v.toString()))
          : <String, String>{};

      final counts = <String, int>{};
      final current = <String, String>{};
      for (final t in _txns) {
        final m = (t['merchant_name'] ?? t['name'] ?? '').toString().trim();
        if (m.isEmpty) continue;
        counts[m] = (counts[m] ?? 0) + 1;
        current.putIfAbsent(
            m, () => rules[m] ?? _prettyCat(t['category']?.toString()));
      }
      final ranked = counts.keys.toList()
        ..sort((a, b) => counts[b]!.compareTo(counts[a]!));
      final merchants = ranked
          .take(40)
          .map((m) => {'name': m, 'current': current[m] ?? 'Uncategorized'})
          .toList();

      final cats = await _categoryList();
      final suggestions = await AiService.categorizeMerchants(
          merchants: merchants, categories: cats);

      // Keep only suggestions that change a known merchant's category.
      final useful = suggestions.where((s) {
        final m = s['merchant'];
        return m != null &&
            current.containsKey(m) &&
            current[m] != s['category'];
      }).toList();

      if (!mounted) return;
      if (useful.isEmpty) {
        setState(() => _messages.add(_Msg('assistant',
            'Your categories already look good — no changes to suggest.')));
      } else {
        setState(() => _messages.add(_Msg('assistant',
            'I have ${useful.length} category suggestion'
            '${useful.length == 1 ? '' : 's'}. Review and apply them below.')));
        _showCategorizeSheet(useful, current);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _messages.add(_Msg('assistant',
            'Categorization failed: '
            '${e.toString().replaceAll('Exception: ', '')}')));
      }
    } finally {
      if (mounted) setState(() => _categorizing = false);
      _scrollToBottom();
    }
  }

  void _showCategorizeSheet(
      List<Map<String, String>> suggestions, Map<String, String> current) {
    final selected = {for (final s in suggestions) s['merchant']!: true};
    showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) {
          final count = selected.values.where((v) => v).length;
          return DraggableScrollableSheet(
            expand: false,
            initialChildSize: 0.7,
            maxChildSize: 0.92,
            builder: (_, scrollCtrl) => Column(
              children: [
                const SizedBox(height: 10),
                Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                        color: Colors.white24,
                        borderRadius: BorderRadius.circular(2))),
                const Padding(
                  padding: EdgeInsets.fromLTRB(20, 16, 20, 6),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text('REVIEW CATEGORIES',
                        style: TextStyle(
                            color: PC.sage,
                            fontSize: 11,
                            letterSpacing: 3,
                            fontWeight: FontWeight.bold)),
                  ),
                ),
                Expanded(
                  child: ListView(
                    controller: scrollCtrl,
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                    children: suggestions.map((s) {
                      final m = s['merchant']!;
                      final on = selected[m] ?? false;
                      return GestureDetector(
                        onTap: () => setSheet(() => selected[m] = !on),
                        behavior: HitTestBehavior.opaque,
                        child: Container(
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: PC.card,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                                color: on
                                    ? PC.pink.withOpacity(0.4)
                                    : Colors.white10),
                          ),
                          child: Row(children: [
                            Icon(
                                on
                                    ? Icons.check_circle
                                    : Icons.radio_button_unchecked,
                                color: on ? PC.pink : PC.sage,
                                size: 20),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(m,
                                      style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 13,
                                          fontWeight: FontWeight.bold),
                                      overflow: TextOverflow.ellipsis),
                                  const SizedBox(height: 3),
                                  Row(children: [
                                    Flexible(
                                      child: Text(
                                          current[m] ?? 'Uncategorized',
                                          overflow: TextOverflow.ellipsis,
                                          style: const TextStyle(
                                              color: PC.sage, fontSize: 11)),
                                    ),
                                    const Padding(
                                      padding: EdgeInsets.symmetric(
                                          horizontal: 6),
                                      child: Icon(Icons.arrow_forward,
                                          color: PC.sage, size: 11),
                                    ),
                                    Flexible(
                                      child: Text(s['category']!,
                                          overflow: TextOverflow.ellipsis,
                                          style: const TextStyle(
                                              color: PC.pink,
                                              fontSize: 11,
                                              fontWeight: FontWeight.bold)),
                                    ),
                                  ]),
                                ],
                              ),
                            ),
                          ]),
                        ),
                      );
                    }).toList(),
                  ),
                ),
                SafeArea(
                  top: false,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                    child: SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: count > 0 ? PC.pink : PC.grove,
                          foregroundColor: PC.background,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12)),
                        ),
                        onPressed: count > 0
                            ? () {
                                Navigator.pop(ctx);
                                _applyCategorizations(suggestions
                                    .where((s) =>
                                        selected[s['merchant']] == true)
                                    .toList());
                              }
                            : null,
                        child: Text(
                          count > 0
                              ? 'APPLY $count RULE${count == 1 ? '' : 'S'}'
                              : 'SELECT SOME TO APPLY',
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, letterSpacing: 2),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _applyCategorizations(
      List<Map<String, String>> accepted) async {
    if (accepted.isEmpty) return;
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('merchant_rules');
    final rules = raw != null
        ? Map<String, dynamic>.from(jsonDecode(raw))
        : <String, dynamic>{};
    for (final s in accepted) {
      rules[s['merchant']!] = s['category']!;
      ApiService.setMerchantCategory(s['merchant']!, s['category']!)
          .catchError((_) {});
    }
    await prefs.setString('merchant_rules', jsonEncode(rules));
    categoriesChanged.value++;
    if (mounted) {
      setState(() => _messages.add(_Msg('assistant',
          'Applied ${accepted.length} category rule'
          '${accepted.length == 1 ? '' : 's'}. They now show on your '
          'Transactions tab.')));
      _scrollToBottom();
    }
  }

  Widget _inputBar() {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
        decoration: const BoxDecoration(
          color: PC.surface,
          border: Border(top: BorderSide(color: Colors.white10)),
        ),
        child: Row(children: [
          Expanded(
            child: TextField(
              controller: _inputCtrl,
              style: const TextStyle(color: Colors.white, fontSize: 14),
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: _sending ? null : _send,
              decoration: InputDecoration(
                hintText: 'Ask about your finances…',
                hintStyle: const TextStyle(color: PC.sage),
                filled: true,
                fillColor: PC.card,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: BorderSide.none),
              ),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _sending ? null : () => _send(_inputCtrl.text),
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: _sending ? PC.grove : PC.pink,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.arrow_upward,
                  color: PC.background, size: 20),
            ),
          ),
        ]),
      ),
    );
  }
}

class _Msg {
  final String role; // 'user' | 'assistant'
  final String text;
  _Msg(this.role, this.text);
}
