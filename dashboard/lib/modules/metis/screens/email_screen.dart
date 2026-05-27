import 'package:flutter/material.dart';
import '../models/reminder.dart';
import '../services/gmail_service.dart';
import '../services/outlook_service.dart';
import '../services/parser.dart';
import '../services/settings_store.dart';
import '../theme.dart';
import '../widgets/common.dart';
import '../widgets/reminder_editor.dart';

class _Candidate {
  final EmailMessage email;
  final ParsedReminder reminder;
  final String provider;
  _Candidate(this.email, this.reminder, this.provider);
}

class EmailScreen extends StatefulWidget {
  const EmailScreen({super.key});

  @override
  State<EmailScreen> createState() => _EmailScreenState();
}

class _EmailScreenState extends State<EmailScreen> {
  bool _gmail = false;
  bool _busy = false;
  String? _error;
  final List<_Candidate> _candidates = [];
  int _scanned = 0;
  bool _devicePollOpen = false;
  late final TextEditingController _clientId;

  bool get _outlook => OutlookService.isSignedIn;

  @override
  void initState() {
    super.initState();
    _clientId = TextEditingController(text: settings.outlookClientId);
    _trySilent();
  }

  @override
  void dispose() {
    _clientId.dispose();
    super.dispose();
  }

  Future<void> _trySilent() async {
    final ok = await GmailService.signInSilently();
    if (mounted) setState(() => _gmail = ok);
  }

  Future<void> _connectGmail() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final ok = await GmailService.signIn();
    if (!mounted) return;
    setState(() {
      _gmail = ok;
      _busy = false;
      if (!ok) _error = 'Gmail connection was cancelled or failed.';
    });
  }

  Future<void> _disconnectGmail() async {
    await GmailService.signOut();
    if (mounted) setState(() => _gmail = false);
  }

  Future<void> _connectOutlook() async {
    await settings.setOutlookClientId(_clientId.text.trim());
    if (settings.outlookClientId.isEmpty) {
      setState(() => _error = 'Paste your Azure app (client) ID first.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final code = await OutlookService.startDeviceLogin();
    if (!mounted) return;
    if (code == null) {
      setState(() {
        _busy = false;
        _error = 'Could not start Outlook sign-in. Check the client ID and '
            'that "Allow public client flows" is enabled in Azure.';
      });
      return;
    }
    final pollFuture = OutlookService.pollForToken(code);
    _devicePollOpen = true;
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => _deviceDialog(ctx, code),
    );
    final ok = await pollFuture;
    if (mounted && _devicePollOpen) {
      _devicePollOpen = false;
      Navigator.of(context).pop();
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (!ok) _error = 'Outlook sign-in was not completed.';
    });
  }

  Future<void> _disconnectOutlook() async {
    await OutlookService.signOut();
    if (mounted) setState(() => _candidates.clear());
  }

  Future<void> _scan() async {
    setState(() {
      _busy = true;
      _error = null;
      _candidates.clear();
    });
    final found = <_Candidate>[];
    var scanned = 0;
    try {
      if (_gmail) {
        final msgs = await GmailService.recentMessages();
        scanned += msgs.length;
        for (final m in msgs) {
          for (final p in await ReminderParser.parseBlock(m.scanText)) {
            if (p.resolved) found.add(_Candidate(m, p, 'Gmail'));
          }
        }
      }
      if (_outlook) {
        final msgs = await OutlookService.recentMessages();
        scanned += msgs.length;
        for (final m in msgs) {
          for (final p in await ReminderParser.parseBlock(m.scanText)) {
            if (p.resolved) found.add(_Candidate(m, p, 'Outlook'));
          }
        }
      }
      await settings.markGmailScanned();
      if (!mounted) return;
      setState(() {
        _candidates
          ..clear()
          ..addAll(found);
        _scanned = scanned;
        _busy = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = 'Could not scan. Check your connection.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final connected = _gmail || _outlook;
    return Scaffold(
      appBar: AppBar(title: const Text('EMAIL')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          SectionLabel('Gmail'),
          _gmail ? _accountCard('Gmail', _disconnectGmail) : _gmailConnect(),
          SectionLabel('Outlook'),
          _outlook
              ? _accountCard('Outlook', _disconnectOutlook)
              : _outlookConnect(),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!,
                style: const TextStyle(color: MC.red, fontSize: 12)),
          ],
          if (connected) ...[
            SectionLabel(
              'Detected items',
              trailing: _scanned > 0
                  ? Text('scanned $_scanned emails',
                      style:
                          const TextStyle(color: MC.muted, fontSize: 10))
                  : null,
            ),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: MC.cyan,
                  side: const BorderSide(color: MC.cyanDim),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: _busy ? null : _scan,
                icon: const Icon(Icons.search, size: 16),
                label: Text(_busy ? 'SCANNING…' : 'SCAN INBOX'),
              ),
            ),
            if (_busy)
              const Padding(
                padding: EdgeInsets.all(40),
                child: Center(
                    child: CircularProgressIndicator(color: MC.cyan)),
              )
            else if (_candidates.isEmpty && _scanned > 0)
              const Padding(
                padding: EdgeInsets.only(top: 20),
                child: EmptyState(
                  icon: Icons.mark_email_read_outlined,
                  title: 'Nothing detected',
                  subtitle:
                      'No deadlines or action items were found in recent emails.',
                ),
              )
            else
              for (final c in _candidates)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _candidateCard(c),
                ),
          ],
        ],
      ),
    );
  }

  Widget _gmailConnect() {
    return MCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Connect Gmail to scan recent emails (read-only) for deadlines '
            'and action items.',
            style: TextStyle(color: MC.muted, fontSize: 12, height: 1.5),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                  backgroundColor: MC.cyan, foregroundColor: MC.bg),
              onPressed: _busy ? null : _connectGmail,
              icon: const Icon(Icons.link, size: 18),
              label: const Text('CONNECT GMAIL',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _outlookConnect() {
    return MCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Connect Outlook via Microsoft sign-in. Paste the Application '
            '(client) ID from your Azure app registration.',
            style: TextStyle(color: MC.muted, fontSize: 12, height: 1.5),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _clientId,
            style: const TextStyle(color: MC.text, fontSize: 13),
            decoration: InputDecoration(
              hintText: 'Azure client ID',
              hintStyle: const TextStyle(color: MC.muted, fontSize: 12),
              filled: true,
              fillColor: MC.surface,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: MC.border)),
              focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: MC.cyan)),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                  backgroundColor: MC.cyan, foregroundColor: MC.bg),
              onPressed: _busy ? null : _connectOutlook,
              icon: const Icon(Icons.link, size: 18),
              label: const Text('CONNECT OUTLOOK',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _accountCard(String provider, Future<void> Function() disconnect) {
    return MCard(
      accent: MC.green,
      child: Row(
        children: [
          const Icon(Icons.mark_email_read, color: MC.green, size: 18),
          const SizedBox(width: 12),
          Expanded(
            child: Text('$provider connected · read-only',
                style: const TextStyle(
                    color: MC.text,
                    fontSize: 13,
                    fontWeight: FontWeight.w600)),
          ),
          GestureDetector(
            onTap: () => disconnect(),
            child: const Padding(
              padding: EdgeInsets.all(6),
              child: Icon(Icons.logout, color: MC.muted, size: 16),
            ),
          ),
        ],
      ),
    );
  }

  Widget _deviceDialog(BuildContext ctx, OutlookDeviceCode code) {
    return AlertDialog(
      backgroundColor: MC.surface,
      title: const Text('Sign in to Outlook',
          style: TextStyle(color: MC.text, fontSize: 15)),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('1.  On any device, open:\n${code.verificationUri}',
              style: const TextStyle(color: MC.muted, fontSize: 12)),
          const SizedBox(height: 12),
          const Text('2.  Enter this code:',
              style: TextStyle(color: MC.muted, fontSize: 12)),
          const SizedBox(height: 6),
          SelectableText(code.userCode,
              style: const TextStyle(
                  color: MC.cyan,
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 3)),
          const SizedBox(height: 14),
          const Row(
            children: [
              SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: MC.cyan)),
              SizedBox(width: 10),
              Text('Waiting for sign-in…',
                  style: TextStyle(color: MC.muted, fontSize: 12)),
            ],
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () {
            _devicePollOpen = false;
            Navigator.pop(ctx);
          },
          child: const Text('CANCEL', style: TextStyle(color: MC.muted)),
        ),
      ],
    );
  }

  Widget _candidateCard(_Candidate c) {
    final r = c.reminder;
    return MCard(
      accent: MC.amber,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(r.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: MC.text,
                        fontSize: 14,
                        fontWeight: FontWeight.w600)),
              ),
              if (r.dueAt != null)
                Text(formatDue(r.dueAt!, hasTime: r.hasTime),
                    style: const TextStyle(color: MC.amber, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 6),
          Text('${c.provider} · from ${c.email.sender}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: MC.muted, fontSize: 11)),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              style: TextButton.styleFrom(foregroundColor: MC.cyan),
              onPressed: () async {
                final saved = await showReminderEditor(
                  context,
                  draft: r,
                  source: ReminderSource.email,
                );
                if (saved != null && mounted) {
                  setState(() => _candidates.remove(c));
                }
              },
              icon: const Icon(Icons.add_alarm, size: 16),
              label: const Text('ADD REMINDER',
                  style: TextStyle(fontSize: 12)),
            ),
          ),
        ],
      ),
    );
  }
}
