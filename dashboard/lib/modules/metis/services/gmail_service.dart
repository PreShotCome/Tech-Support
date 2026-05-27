import 'package:extension_google_sign_in_as_googleapis_auth/extension_google_sign_in_as_googleapis_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:googleapis/gmail/v1.dart' as gmail;

/// A lightweight view of one Gmail message.
class EmailMessage {
  final String id;
  final String subject;
  final String from;
  final String snippet;
  final DateTime date;

  EmailMessage({
    required this.id,
    required this.subject,
    required this.from,
    required this.snippet,
    required this.date,
  });

  /// Sender name without the angle-bracketed address.
  String get sender {
    final lt = from.indexOf('<');
    final name = lt > 0 ? from.substring(0, lt).trim() : from.trim();
    return name.replaceAll('"', '').isEmpty ? from : name.replaceAll('"', '');
  }

  /// The text fed to the parser when looking for deadlines/action items.
  String get scanText => '$subject. $snippet';
}

/// Read-only Gmail access for surfacing deadlines and action items.
class GmailService {
  static final GoogleSignIn _signIn = GoogleSignIn(
    scopes: const [gmail.GmailApi.gmailReadonlyScope],
  );

  static GoogleSignInAccount? get account => _signIn.currentUser;
  static bool get isSignedIn => _signIn.currentUser != null;

  static Future<bool> signInSilently() async {
    final acc = await _signIn.signInSilently();
    return acc != null;
  }

  static Future<bool> signIn() async {
    try {
      final acc = await _signIn.signIn();
      return acc != null;
    } catch (_) {
      return false;
    }
  }

  static Future<void> signOut() => _signIn.signOut();

  /// Fetches recent primary-inbox messages with metadata + snippet.
  static Future<List<EmailMessage>> recentMessages({int max = 20}) async {
    final client = await _signIn.authenticatedClient();
    if (client == null) return const [];

    final api = gmail.GmailApi(client);
    final listed = await api.users.messages.list(
      'me',
      maxResults: max,
      q: 'newer_than:7d -in:chats category:primary',
    );

    final out = <EmailMessage>[];
    for (final ref in listed.messages ?? const <gmail.Message>[]) {
      if (ref.id == null) continue;
      final full = await api.users.messages.get(
        'me',
        ref.id!,
        format: 'metadata',
        metadataHeaders: ['Subject', 'From', 'Date'],
      );
      final headers = <String, String>{
        for (final h in full.payload?.headers ?? const <gmail.MessagePartHeader>[])
          if (h.name != null) h.name!: h.value ?? '',
      };
      out.add(EmailMessage(
        id: ref.id!,
        subject: headers['Subject'] ?? '(no subject)',
        from: headers['From'] ?? '',
        snippet: _decode(full.snippet ?? ''),
        date: DateTime.fromMillisecondsSinceEpoch(
            int.tryParse(full.internalDate ?? '0') ?? 0),
      ));
    }
    return out;
  }

  static String _decode(String s) =>
      s.replaceAll('&#39;', "'").replaceAll('&quot;', '"').replaceAll('&amp;', '&');
}
