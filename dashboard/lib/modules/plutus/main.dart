import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'screens/dashboard_screen.dart';
import 'screens/bills_screen.dart';
import 'screens/accounts_screen.dart';
import 'screens/transactions_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/paycheck_screen.dart';
import 'screens/calendar_screen.dart';
import 'screens/safe_to_spend_screen.dart';
import 'screens/assistant_screen.dart';
import 'screens/login_screen.dart';
import 'services/api_service.dart';
import 'services/auth_service.dart';

// main() stripped — module loaded via dashboard entry.dart
// ── Colour palette ────────────────────────────────────────────────────────

class PC {
  static const background = Color(0xFF0B1E12);
  static const surface    = Color(0xFF162B1C);
  static const card       = Color(0xFF1C1838);
  static const grove      = Color(0xFF2C2850);
  static const pink       = Color(0xFFFFB7C5);
  static const pinkBright = Color(0xFFFFC9D4);
  static const gold       = Color(0xFFC9A227);
  static const sage       = Color(0xFF9B93B8);
  static const red        = Color(0xFFFF6B6B);
  static const green      = Color(0xFF4CAF50);
}

// ── Cross-screen navigation ───────────────────────────────────────────────
// Set this to a tab id (e.g. 'safetospend') to ask the shell to switch tabs.
final ValueNotifier<String?> navRequest = ValueNotifier<String?>(null);

// Bumped whenever merchant category rules change, so screens reload them.
final ValueNotifier<int> categoriesChanged = ValueNotifier<int>(0);

// Bumped when the paycheck schedule changes, so screens reload it.
final ValueNotifier<int> paycheckChanged = ValueNotifier<int>(0);

// Set true to ask the Paycheck screen to open its configure sheet.
final ValueNotifier<bool> requestPaycheckConfig = ValueNotifier<bool>(false);

// ── Nav screen definitions ────────────────────────────────────────────────

class _NavDef {
  final String id, label;
  final IconData icon, selIcon;
  const _NavDef(this.id, this.label, this.icon, this.selIcon);
}

const _allNavDefs = [
  _NavDef('dashboard',    'Overview',     Icons.dashboard_outlined,      Icons.dashboard),
  _NavDef('safetospend',  'Spendable',    Icons.account_balance_wallet_outlined, Icons.account_balance_wallet),
  _NavDef('assistant',    'Assistant',    Icons.auto_awesome_outlined,   Icons.auto_awesome),
  _NavDef('transactions', 'Transactions', Icons.list_alt_outlined,       Icons.list_alt),
  _NavDef('bills',        'Bills',        Icons.receipt_long_outlined,   Icons.receipt_long),
  _NavDef('paycheck',     'Paycheck',     Icons.payments_outlined,       Icons.payments),
  _NavDef('accounts',     'Accounts',     Icons.account_balance_outlined,Icons.account_balance),
  _NavDef('calendar',     'Calendar',     Icons.calendar_month_outlined, Icons.calendar_month),
  _NavDef('settings',     'Settings',     Icons.settings_outlined,       Icons.settings),
];

const _defaultPrimary = ['safetospend', 'bills', 'accounts'];

// ── App ───────────────────────────────────────────────────────────────────

class PlutuApp extends StatelessWidget {
  const PlutuApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Plutus',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        scaffoldBackgroundColor: PC.background,
        colorScheme: const ColorScheme.dark(
          primary: PC.pink,
          secondary: PC.gold,
          surface: PC.surface,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: PC.background,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: PC.sage,
            fontSize: 13,
            fontWeight: FontWeight.bold,
            letterSpacing: 3,
          ),
          iconTheme: IconThemeData(color: PC.sage),
        ),
        dividerColor: Colors.white10,
        useMaterial3: true,
      ),
      home: const AuthGate(),
    );
  }
}

// ── Auth gate ─────────────────────────────────────────────────────────────
// Shows the login screen until a user is signed in, then the app shell.

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: AuthService.authStateChanges,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            backgroundColor: PC.background,
            body: Center(child: CircularProgressIndicator(color: PC.pink)),
          );
        }
        return snap.data == null ? const LoginScreen() : const MainShell();
      },
    );
  }
}

// ── Main shell ────────────────────────────────────────────────────────────

class MainShell extends StatefulWidget {
  const MainShell({super.key});
  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  String _currentId = 'dashboard';
  List<String> _primaryIds = List.from(_defaultPrimary);

  static final _screenMap = {
    'dashboard':    const DashboardScreen(),
    'safetospend':  const SafeToSpendScreen(),
    'assistant':    const AssistantScreen(),
    'transactions': const TransactionsScreen(),
    'bills':        const BillsScreen(),
    'paycheck':     const PaycheckScreen(),
    'accounts':     const AccountsScreen(),
    'calendar':     const CalendarScreen(),
    'settings':     const SettingsScreen(),
  };

  static const _allIds = [
    'dashboard', 'safetospend', 'assistant', 'transactions', 'bills', 'paycheck', 'accounts', 'calendar', 'settings'
  ];

  @override
  void initState() {
    super.initState();
    _loadNavPrefs();
    navRequest.addListener(_handleNavRequest);
    // Background sync on every launch — fire and forget
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ApiService.sync().catchError((_) => <String, dynamic>{});
    });
  }

  @override
  void dispose() {
    navRequest.removeListener(_handleNavRequest);
    super.dispose();
  }

  void _handleNavRequest() {
    final target = navRequest.value;
    if (target != null && _allIds.contains(target)) {
      _navigate(target);
      navRequest.value = null;
    }
  }

  Future<void> _loadNavPrefs() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString('primary_tab_ids');
    if (raw != null) {
      var decoded = List<String>.from(jsonDecode(raw));
      // One-time migration: surface the Safe-to-Spend tab for installs that
      // saved their nav layout before this tab existed.
      if (!(p.getBool('nav_migrated_sts') ?? false)) {
        if (!decoded.contains('safetospend')) {
          decoded = ['safetospend', ...decoded];
        }
        await p.setBool('nav_migrated_sts', true);
      }
      // Dashboard is always pinned — exclude it from configurable slots
      final valid = decoded
          .where((id) => id != 'dashboard' && _allIds.contains(id))
          .toList();
      if (valid.length >= 3) {
        final trimmed = valid.take(3).toList();
        if (jsonEncode(trimmed) != raw) {
          await p.setString('primary_tab_ids', jsonEncode(trimmed));
        }
        if (mounted) setState(() => _primaryIds = trimmed);
        return;
      }
    }
    if (mounted) setState(() => _primaryIds = List.from(_defaultPrimary));
  }

  Future<void> _saveNavPrefs(List<String> ids) async {
    final p = await SharedPreferences.getInstance();
    await p.setString('primary_tab_ids', jsonEncode(ids));
    setState(() => _primaryIds = ids);
  }

  void _navigate(String id) {
    setState(() => _currentId = id);
    _loadNavPrefs();
  }

  int get _navIndex {
    if (_currentId == 'dashboard') return 0;
    final idx = _primaryIds.indexOf(_currentId);
    return idx >= 0 ? idx + 1 : 4;
  }

  void _showMore(BuildContext context) {
    final secondary = _allNavDefs
        .where((d) => d.id != 'dashboard' && !_primaryIds.contains(d.id))
        .toList();
    showModalBottomSheet(
      context: context,
      backgroundColor: PC.surface,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => SafeArea(
        top: false,
        child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(height: 8),
          Container(width: 40, height: 4,
              decoration: BoxDecoration(color: Colors.white24,
                  borderRadius: BorderRadius.circular(2))),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
            child: Row(children: [
              const Text('MORE', style: TextStyle(color: PC.sage, fontSize: 11,
                  letterSpacing: 3, fontWeight: FontWeight.bold)),
              const Spacer(),
              TextButton.icon(
                style: TextButton.styleFrom(foregroundColor: PC.pink),
                onPressed: () {
                  Navigator.pop(ctx);
                  _showNavCustomizer(context);
                },
                icon: const Icon(Icons.tune, size: 14),
                label: const Text('Customize', style: TextStyle(fontSize: 12)),
              ),
            ]),
          ),
          GridView.count(
            crossAxisCount: 4,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
            children: secondary.map((def) {
              final isActive = _currentId == def.id;
              return GestureDetector(
                onTap: () {
                  Navigator.pop(ctx);
                  _navigate(def.id);
                },
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Container(
                    width: 52, height: 52,
                    decoration: BoxDecoration(
                      color: isActive ? PC.pink.withOpacity(0.15) : PC.card,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: isActive ? PC.pink.withOpacity(0.4) : Colors.white10),
                    ),
                    child: Icon(isActive ? def.selIcon : def.icon,
                        color: isActive ? PC.pink : PC.sage, size: 22),
                  ),
                  const SizedBox(height: 6),
                  Text(def.label,
                      style: TextStyle(
                          color: isActive ? PC.pink : PC.sage,
                          fontSize: 10, fontWeight: FontWeight.bold),
                      textAlign: TextAlign.center),
                ]),
              );
            }).toList(),
          ),
        ],
      ),
      ),
    );
  }

  void _showNavCustomizer(BuildContext context) {
    List<String> draft = List.from(_primaryIds);

    showModalBottomSheet(
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
              const Text('Choose 3 tabs beside Dashboard.',
                  style: TextStyle(color: PC.sage, fontSize: 12)),
              const SizedBox(height: 16),
              ..._allNavDefs.where((d) => d.id != 'dashboard').map((def) {
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
                          decoration: BoxDecoration(
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
                  onPressed: draft.length == 3 ? () {
                    Navigator.pop(ctx);
                    _saveNavPrefs(draft);
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
    final screens = _allIds.map((id) => _screenMap[id]!).toList();

    return Scaffold(
      body: IndexedStack(
        index: _allIds.indexOf(_currentId),
        children: screens,
      ),
      bottomNavigationBar: NavigationBar(
        backgroundColor: PC.surface,
        indicatorColor: PC.pink.withOpacity(0.2),
        selectedIndex: _navIndex,
        onDestinationSelected: (i) {
          if (i == 0) {
            _navigate('dashboard');
          } else if (i <= 3) {
            _navigate(_primaryIds[i - 1]);
          } else {
            _showMore(context);
          }
        },
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard, color: PC.pink),
            label: 'Overview',
          ),
          ..._primaryIds.map((id) {
            final def = _allNavDefs.firstWhere((d) => d.id == id);
            return NavigationDestination(
              icon: Icon(def.icon),
              selectedIcon: Icon(def.selIcon, color: PC.pink),
              label: def.label,
            );
          }),
          NavigationDestination(
            icon: const Icon(Icons.apps_outlined),
            selectedIcon: Icon(Icons.apps,
                color: _navIndex == 4 ? PC.pink : PC.sage),
            label: 'More',
          ),
        ],
      ),
    );
  }
}
