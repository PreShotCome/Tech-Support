import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import '../models/reminder.dart';
import '../services/parser.dart';
import '../services/speech_service.dart';
import '../theme.dart';
import 'reminder_editor.dart';

/// The capture entry point: tap the mic to record by voice, long-press to
/// type instead. Either way the input is parsed and confirmed in the editor.
class CaptureFab extends StatelessWidget {
  const CaptureFab({super.key});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onLongPress: () => _captureText(context),
      child: FloatingActionButton.extended(
        backgroundColor: MC.cyan,
        foregroundColor: MC.bg,
        onPressed: () => _captureVoice(context),
        icon: const Icon(Icons.mic),
        label: const Text('CAPTURE',
            style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1)),
      ),
    );
  }

  Future<void> _captureVoice(BuildContext context) async {
    final status = await Permission.microphone.request();
    if (!context.mounted) return;
    if (!status.isGranted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Microphone permission is needed to record.'),
      ));
      return;
    }
    final transcript = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: MC.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (_) => const _RecordingSheet(),
    );
    if (!context.mounted) return;
    await _process(context, transcript, ReminderSource.voice);
  }

  Future<void> _captureText(BuildContext context) async {
    final controller = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: MC.surface,
        title: const Text('Type a reminder',
            style: TextStyle(color: MC.text, fontSize: 15)),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLines: 3,
          style: const TextStyle(color: MC.text, fontSize: 14),
          decoration: const InputDecoration(
            hintText: 'e.g. call the dentist tomorrow at 10am',
            hintStyle: TextStyle(color: MC.muted, fontSize: 12),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('CANCEL', style: TextStyle(color: MC.muted)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, controller.text),
            child: const Text('NEXT', style: TextStyle(color: MC.cyan)),
          ),
        ],
      ),
    );
    if (!context.mounted) return;
    await _process(context, text, ReminderSource.text);
  }

  Future<void> _process(
      BuildContext context, String? raw, ReminderSource source) async {
    if (raw == null || raw.trim().isEmpty) return;
    final parsed = await ReminderParser.parseCapture(raw);
    if (!context.mounted) return;
    await showReminderEditor(context, draft: parsed, source: source);
  }
}

class _RecordingSheet extends StatefulWidget {
  const _RecordingSheet();

  @override
  State<_RecordingSheet> createState() => _RecordingSheetState();
}

class _RecordingSheetState extends State<_RecordingSheet> {
  String _text = '';
  bool _listening = true;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    final ok = await speechService.start(
      onResult: (t, _) {
        if (mounted) setState(() => _text = t);
      },
      onDone: () {
        if (mounted) setState(() => _listening = false);
      },
    );
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Speech recognition is unavailable on this device.'),
      ));
      Navigator.pop(context);
    }
  }

  void _finish() {
    speechService.stop();
    Navigator.pop(context, _text.trim());
  }

  @override
  void dispose() {
    speechService.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 22, 24, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 76,
            height: 76,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: (_listening ? MC.cyan : MC.cyanDim).withOpacity(0.16),
              border: Border.all(
                  color: _listening ? MC.cyan : MC.cyanDim, width: 2),
            ),
            child: Icon(_listening ? Icons.mic : Icons.mic_off,
                color: _listening ? MC.cyan : MC.muted, size: 32),
          ),
          const SizedBox(height: 16),
          Text(_listening ? 'LISTENING…' : 'STOPPED',
              style: TextStyle(
                  color: _listening ? MC.cyan : MC.muted,
                  fontSize: 12,
                  letterSpacing: 2,
                  fontWeight: FontWeight.bold)),
          const SizedBox(height: 14),
          Container(
            width: double.infinity,
            constraints: const BoxConstraints(minHeight: 60),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: MC.card,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: MC.border),
            ),
            child: Text(
              _text.isEmpty ? 'Speak now — your words appear here.' : _text,
              style: TextStyle(
                  color: _text.isEmpty ? MC.muted : MC.text,
                  fontSize: 14,
                  height: 1.4),
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: MC.muted,
                    side: const BorderSide(color: MC.border),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: () {
                    speechService.cancel();
                    Navigator.pop(context);
                  },
                  child: const Text('CANCEL'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: MC.cyan,
                    foregroundColor: MC.bg,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: _text.trim().isEmpty ? null : _finish,
                  child: const Text('DONE',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
