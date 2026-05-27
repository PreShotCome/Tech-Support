import 'package:flutter/material.dart';
import '../models/reminder.dart';
import '../services/reminder_repository.dart';
import '../theme.dart';
import 'common.dart';

/// Bottom-sheet editor for creating or editing a reminder. Used after every
/// capture to confirm the parsed result, and from the reminder list to edit.
Future<Reminder?> showReminderEditor(
  BuildContext context, {
  Reminder? existing,
  ParsedReminder? draft,
  ReminderSource source = ReminderSource.text,
}) {
  return showModalBottomSheet<Reminder>(
    context: context,
    backgroundColor: MC.surface,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
    ),
    builder: (ctx) => _EditorSheet(
      existing: existing,
      draft: draft,
      source: source,
    ),
  );
}

class _EditorSheet extends StatefulWidget {
  final Reminder? existing;
  final ParsedReminder? draft;
  final ReminderSource source;
  const _EditorSheet({this.existing, this.draft, required this.source});

  @override
  State<_EditorSheet> createState() => _EditorSheetState();
}

class _EditorSheetState extends State<_EditorSheet> {
  late final TextEditingController _title;
  late final TextEditingController _notes;
  late DateTime _due;
  late bool _hasTime;
  bool _saving = false;
  String? _error;

  bool get _isEdit => widget.existing != null;
  bool get _unresolved => widget.draft != null && !widget.draft!.resolved;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    final d = widget.draft;
    _title = TextEditingController(text: e?.title ?? d?.title ?? '');
    _notes = TextEditingController(text: e?.notes ?? d?.notes ?? '');
    _hasTime = e?.hasTime ?? d?.hasTime ?? true;
    _due = e?.dueAt ??
        d?.dueAt ??
        DateTime.now().add(const Duration(hours: 1));
  }

  @override
  void dispose() {
    _title.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _due,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 365 * 3)),
    );
    if (picked != null) {
      setState(() => _due =
          DateTime(picked.year, picked.month, picked.day, _due.hour, _due.minute));
    }
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_due),
    );
    if (picked != null) {
      setState(() {
        _due = DateTime(
            _due.year, _due.month, _due.day, picked.hour, picked.minute);
        _hasTime = true;
      });
    }
  }

  Future<void> _save() async {
    final title = _title.text.trim();
    if (title.isEmpty) {
      setState(() => _error = 'Give the reminder a title.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final Reminder result;
      if (_isEdit) {
        final r = widget.existing!
          ..title = title
          ..notes = _notes.text.trim()
          ..dueAt = _due
          ..hasTime = _hasTime;
        await reminders.save(r);
        result = r;
      } else {
        result = await reminders.add(Reminder(
          title: title,
          notes: _notes.text.trim(),
          dueAt: _due,
          hasTime: _hasTime,
          source: widget.source,
          rawInput: widget.draft != null ? widget.draft!.title : title,
        ));
      }
      if (mounted) Navigator.pop(context, result);
    } catch (e, st) {
      // Surface the real failure in the sheet so it cannot be missed.
      if (mounted) {
        setState(() {
          _saving = false;
          _error = '$e\n\n$st';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 18, 20, 18 + bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 38,
              height: 4,
              decoration: BoxDecoration(
                  color: MC.border,
                  borderRadius: BorderRadius.circular(2)),
            ),
          ),
          const SizedBox(height: 16),
          Text(_isEdit ? 'EDIT REMINDER' : 'NEW REMINDER',
              style: const TextStyle(
                  color: MC.cyan,
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 2)),
          if (_unresolved) ...[
            const SizedBox(height: 6),
            const Text(
              "Couldn't pin down a time — set one below.",
              style: TextStyle(color: MC.amber, fontSize: 11),
            ),
          ],
          const SizedBox(height: 16),
          _field(_title, 'What to be reminded about', autofocus: !_isEdit),
          const SizedBox(height: 10),
          _field(_notes, 'Notes (optional)', maxLines: 2),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _chip(
                  icon: Icons.event_outlined,
                  label: formatDue(_due, hasTime: false),
                  onTap: _pickDate,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _chip(
                  icon: Icons.schedule_outlined,
                  label: _hasTime
                      ? TimeOfDay.fromDateTime(_due).format(context)
                      : 'All day',
                  onTap: _pickTime,
                ),
              ),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: 14),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: MC.red.withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: MC.red),
              ),
              child: SelectableText(
                _error!,
                style: const TextStyle(
                    color: MC.red, fontSize: 11, height: 1.4),
              ),
            ),
          ],
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: MC.cyan,
                foregroundColor: MC.bg,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: _saving ? null : _save,
              child: Text(_saving ? 'SAVING…' : 'SAVE REMINDER',
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, letterSpacing: 1.5)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _field(TextEditingController c, String hint,
      {int maxLines = 1, bool autofocus = false}) {
    return TextField(
      controller: c,
      autofocus: autofocus,
      maxLines: maxLines,
      style: const TextStyle(color: MC.text, fontSize: 14),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: MC.muted, fontSize: 13),
        filled: true,
        fillColor: MC.card,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: MC.border)),
        focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: MC.cyan)),
      ),
    );
  }

  Widget _chip(
      {required IconData icon,
      required String label,
      required VoidCallback onTap}) {
    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: MC.card,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: MC.border),
        ),
        child: Row(
          children: [
            Icon(icon, color: MC.cyan, size: 16),
            const SizedBox(width: 8),
            Expanded(
              child: Text(label,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: MC.text, fontSize: 12)),
            ),
          ],
        ),
      ),
    );
  }
}
