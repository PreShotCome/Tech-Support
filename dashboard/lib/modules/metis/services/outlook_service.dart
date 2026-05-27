import 'dart:convert';
import 'package:http/http.dart' as http;
import 'gmail_service.dart' show EmailMessage;
import 'settings_store.dart';

/// One step of the Microsoft device-code sign-in flow.
class OutlookDeviceCode {
  final String userCode;
  final String verificationUri;
  final String deviceCode;
  final int interval;
  OutlookDeviceCode({
    required this.userCode,
    required this.verificationUri,
    required this.deviceCode,
    required this.interval,
  });
}

/// Read-only Outlook / Microsoft 365 mail access via Microsoft Graph.
///
/// Uses the OAuth device-code flow: no webview, no redirect URIs, no native
/// config. The user registers an app in Azure (public client, with the
/// Mail.Read + offline_access delegated permissions) and pastes its
/// Application (client) ID.
class OutlookService {
  static const _authority =
      'https://login.microsoftonline.com/common/oauth2/v2.0';
  static const _scope = 'offline_access Mail.Read';

  static String _accessToken = '';
  static DateTime _expiry = DateTime.utc(2000);

  static bool get isSignedIn => settings.outlookRefreshToken.isNotEmpty;

  /// Begins sign-in. Returns the code to show the user, or null on failure.
  static Future<OutlookDeviceCode?> startDeviceLogin() async {
    final clientId = settings.outlookClientId.trim();
    if (clientId.isEmpty) return null;
    try {
      final res = await http.post(
        Uri.parse('$_authority/devicecode'),
        body: {'client_id': clientId, 'scope': _scope},
      ).timeout(const Duration(seconds: 20));
      if (res.statusCode != 200) return null;
      final j = jsonDecode(res.body) as Map<String, dynamic>;
      return OutlookDeviceCode(
        userCode: j['user_code'] as String,
        verificationUri: j['verification_uri'] as String,
        deviceCode: j['device_code'] as String,
        interval: (j['interval'] as int?) ?? 5,
      );
    } catch (_) {
      return null;
    }
  }

  /// Polls until the user authorizes in their browser. True on success.
  static Future<bool> pollForToken(OutlookDeviceCode code) async {
    final clientId = settings.outlookClientId.trim();
    final deadline = DateTime.now().add(const Duration(minutes: 10));
    var wait = code.interval;
    while (DateTime.now().isBefore(deadline)) {
      await Future.delayed(Duration(seconds: wait));
      try {
        final res = await http.post(
          Uri.parse('$_authority/token'),
          body: {
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
            'client_id': clientId,
            'device_code': code.deviceCode,
          },
        ).timeout(const Duration(seconds: 20));
        final j = jsonDecode(res.body) as Map<String, dynamic>;
        if (res.statusCode == 200) {
          _store(j);
          return true;
        }
        final err = j['error'] as String?;
        if (err == 'authorization_pending') continue;
        if (err == 'slow_down') {
          wait += 5;
          continue;
        }
        return false; // expired_token / access_denied / bad client id
      } catch (_) {
        // transient — keep polling
      }
    }
    return false;
  }

  static Future<bool> _ensureToken() async {
    if (_accessToken.isNotEmpty && DateTime.now().isBefore(_expiry)) {
      return true;
    }
    final refresh = settings.outlookRefreshToken;
    if (refresh.isEmpty) return false;
    try {
      final res = await http.post(
        Uri.parse('$_authority/token'),
        body: {
          'grant_type': 'refresh_token',
          'client_id': settings.outlookClientId.trim(),
          'refresh_token': refresh,
          'scope': _scope,
        },
      ).timeout(const Duration(seconds: 20));
      if (res.statusCode != 200) return false;
      _store(jsonDecode(res.body) as Map<String, dynamic>);
      return true;
    } catch (_) {
      return false;
    }
  }

  static void _store(Map<String, dynamic> j) {
    _accessToken = j['access_token'] as String? ?? '';
    final ttl = (j['expires_in'] as int?) ?? 3600;
    _expiry = DateTime.now().add(Duration(seconds: ttl - 60));
    final refresh = j['refresh_token'] as String?;
    if (refresh != null && refresh.isNotEmpty) {
      settings.setOutlookRefreshToken(refresh);
    }
  }

  static Future<void> signOut() async {
    _accessToken = '';
    _expiry = DateTime.utc(2000);
    await settings.setOutlookRefreshToken('');
  }

  /// Recent inbox messages, newest first. Returns [] on any failure.
  static Future<List<EmailMessage>> recentMessages({int max = 20}) async {
    if (!await _ensureToken()) return const [];
    try {
      final res = await http.get(
        Uri.parse('https://graph.microsoft.com/v1.0/me/messages'
            '?\$top=$max&\$select=subject,from,bodyPreview,receivedDateTime'),
        headers: {'Authorization': 'Bearer $_accessToken'},
      ).timeout(const Duration(seconds: 20));
      if (res.statusCode != 200) return const [];
      final j = jsonDecode(res.body) as Map<String, dynamic>;
      final out = <EmailMessage>[];
      for (final m in (j['value'] as List? ?? const [])) {
        final map = m as Map<String, dynamic>;
        final from = map['from'] as Map<String, dynamic>?;
        final addr = from?['emailAddress'] as Map<String, dynamic>?;
        out.add(EmailMessage(
          id: map['id'] as String? ?? '',
          subject: map['subject'] as String? ?? '(no subject)',
          from: (addr?['name'] as String?) ??
              (addr?['address'] as String?) ??
              '',
          snippet: map['bodyPreview'] as String? ?? '',
          date: DateTime.tryParse(
                  map['receivedDateTime'] as String? ?? '') ??
              DateTime.now(),
        ));
      }
      return out;
    } catch (_) {
      return const [];
    }
  }
}
