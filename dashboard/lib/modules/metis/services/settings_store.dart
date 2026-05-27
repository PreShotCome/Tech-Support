import 'package:shared_preferences/shared_preferences.dart';

/// Persistent app settings. Claude API usage is fully optional and off by
/// default — the built-in heuristic parser handles capture on its own.
class SettingsStore {
  static const _kClaudeKey      = 'claude_api_key';
  static const _kClaudeEnabled  = 'claude_enabled';
  static const _kClaudeModel    = 'claude_model';
  static const _kForeground     = 'foreground_enabled';
  static const _kGmailScanned   = 'gmail_last_scan';
  static const _kTimezone       = 'timezone';
  static const _kOutlookClient  = 'outlook_client_id';
  static const _kOutlookRefresh = 'outlook_refresh_token';

  String claudeApiKey  = '';
  bool   claudeEnabled = false;
  String claudeModel   = 'claude-opus-4-7';
  bool   foregroundEnabled = true;
  DateTime? gmailLastScan;

  /// IANA timezone name (e.g. America/Los_Angeles). Empty means auto-detect.
  String timezone = '';

  /// Azure app (client) ID and the stored Outlook refresh token.
  String outlookClientId = '';
  String outlookRefreshToken = '';

  bool get claudeAvailable => claudeEnabled && claudeApiKey.trim().isNotEmpty;

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    claudeApiKey        = p.getString(_kClaudeKey) ?? '';
    claudeEnabled       = p.getBool(_kClaudeEnabled) ?? false;
    claudeModel         = p.getString(_kClaudeModel) ?? 'claude-opus-4-7';
    foregroundEnabled   = p.getBool(_kForeground) ?? true;
    timezone            = p.getString(_kTimezone) ?? '';
    outlookClientId     = p.getString(_kOutlookClient) ?? '';
    outlookRefreshToken = p.getString(_kOutlookRefresh) ?? '';
    final scan = p.getInt(_kGmailScanned);
    gmailLastScan = scan == null
        ? null
        : DateTime.fromMillisecondsSinceEpoch(scan);
  }

  Future<void> setClaudeApiKey(String v) async {
    claudeApiKey = v.trim();
    final p = await SharedPreferences.getInstance();
    await p.setString(_kClaudeKey, claudeApiKey);
  }

  Future<void> setClaudeEnabled(bool v) async {
    claudeEnabled = v;
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kClaudeEnabled, v);
  }

  Future<void> setClaudeModel(String v) async {
    claudeModel = v.trim().isEmpty ? 'claude-opus-4-7' : v.trim();
    final p = await SharedPreferences.getInstance();
    await p.setString(_kClaudeModel, claudeModel);
  }

  Future<void> setForegroundEnabled(bool v) async {
    foregroundEnabled = v;
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kForeground, v);
  }

  Future<void> setTimezone(String v) async {
    timezone = v;
    final p = await SharedPreferences.getInstance();
    await p.setString(_kTimezone, v);
  }

  Future<void> setOutlookClientId(String v) async {
    outlookClientId = v.trim();
    final p = await SharedPreferences.getInstance();
    await p.setString(_kOutlookClient, outlookClientId);
  }

  Future<void> setOutlookRefreshToken(String v) async {
    outlookRefreshToken = v;
    final p = await SharedPreferences.getInstance();
    await p.setString(_kOutlookRefresh, v);
  }

  Future<void> markGmailScanned() async {
    gmailLastScan = DateTime.now();
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kGmailScanned, gmailLastScan!.millisecondsSinceEpoch);
  }
}

final settings = SettingsStore();
