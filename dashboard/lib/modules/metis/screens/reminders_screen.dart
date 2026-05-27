import 'package:flutter/material.dart';
import '../models/reminder.dart';
import '../services/reminder_repository.dart';
import '../theme.dart';
import '../widgets/capture_fab.dart';
import '../widgets/common.dart';
import '../widgets/reminder_editor.dart';

class RemindersScreen extends StatelessWidget {
  const RemindersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('METIS'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'New reminder',
            onPressed: () => showReminderEditor(context),
          ),
        ],
      ),
      floatingActionButton: const CaptureFab(),
      body: ListenableBuilder(
        listenable: reminders,
        builder: (context, _) {
          final pending = reminders.pending;
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
            children: [
              _statsRow(),
              if (pending.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 80),
                  child: EmptyState(
                    icon: Icons.notifications_none,
                    title: 'Nothing scheduled',
                    subtitle:
                        'Tap + at the top to add a reminder, or use CAPTURE to record one by voice.',
                  ),
                )
              else
                ..._groups(pending),
            ],
          );
        },
      ),
    );
  }

  Widget _statsRow() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          _stat('${reminders.todayCount}', 'TODAY', MC.cyan),
          const SizedBox(width: 10),
          _stat('${reminders.overdueCount}', 'OVERDUE', MC.red),
          const SizedBox(width: 10),
          _stat('${reminders.pendingCount}', 'PENDING', MC.muted),
        ],
      ),
    );
  }

  Widget _stat(String value, String label, Color color) {
    return Expanded(
      child: MCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value,
                style: TextStyle(
                    color: color,
                    fontSize: 22,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 2),
            Text(label,
                style: const TextStyle(color: MC.muted, fontSize: 10)),
          ],
        ),
      ),
    );
  }

  List<Widget> _groups(List<Reminder> pending) {
    final now = DateTime.now();
    final endToday = DateTime(now.year, now.month, now.day, 23, 59, 59);
    final endWeek = now.add(const Duration(days: 7));

    final overdue = <Reminder>[];
    final today = <Reminder>[];
    final week = <Reminder>[];
    final later = <Reminder>[];
    for (final r in pending) {
      if (r.dueAt.isBefore(now)) {
        overdue.add(r);
      } else if (!r.dueAt.isAfter(endToday)) {
        today.add(r);
      } else if (r.dueAt.isBefore(endWeek)) {
        week.add(r);
      } else {
        later.add(r);
      }
    }

    final widgets = <Widget>[];
    void section(String label, List<Reminder> list) {
      if (list.isEmpty) return;
      widgets.add(SectionLabel(label));
      for (final r in list) {
        widgets.add(Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: _ReminderCard(reminder: r),
        ));
      }
    }

    section('Overdue', overdue);
    section('Today', today);
    section('This week', week);
    section('Later', later);
    return widgets;
  }
}

class _ReminderCard extends StatelessWidget {
  final Reminder reminder;
  const _ReminderCard({required this.reminder});

  static const _sourceIcon = {
    ReminderSource.voice: Icons.mic,
    ReminderSource.text: Icons.keyboard,
    ReminderSource.email: Icons.mail_outline,
  };

  void _complete(BuildContext context) {
    reminders.setStatus(reminder, ReminderStatus.completed);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('Completed: ${reminder.title}'),
      action: SnackBarAction(
        label: 'UNDO',
        textColor: MC.cyan,
        onPressed: () =>
            reminders.setStatus(reminder, ReminderStatus.pending),
      ),
    ));
  }

  void _menu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: MC.surface,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _action(ctx, Icons.edit_outlined, 'Edit', () {
              Navigator.pop(ctx);
              showReminderEditor(context, existing: reminder);
            }),
            _action(ctx, Icons.snooze_outlined, 'Snooze 1 hour', () {
              Navigator.pop(ctx);
              reminder.dueAt =
                  DateTime.now().add(const Duration(hours: 1));
              reminders.save(reminder);
            }),
            _action(ctx, Icons.cancel_outlined, 'Dismiss', () {
              Navigator.pop(ctx);
              reminders.setStatus(reminder, ReminderStatus.dismissed);
            }),
            _action(ctx, Icons.delete_outline, 'Delete', () {
              Navigator.pop(ctx);
              reminders.delete(reminder);
            }, danger: true),
          ],
        ),
      ),
    );
  }

  Widget _action(BuildContext ctx, IconData icon, String label,
      VoidCallback onTap,
      {bool danger = false}) {
    final color = danger ? MC.red : MC.text;
    return ListTile(
      leading: Icon(icon, color: color, size: 20),
      title: Text(label, style: TextStyle(color: color, fontSize: 14)),
      onTap: onTap,
    );
  }

  @override
  Widget build(BuildContext context) {
    final overdue = reminder.isOverdue;
    return MCard(
      accent: overdue ? MC.red : MC.cyan,
      onTap: () => showReminderEditor(context, existing: reminder),
      child: Row(
        children: [
          Icon(_sourceIcon[reminder.source], color: MC.muted, size: 16),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(reminder.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: MC.text,
                        fontSize: 14,
                        fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(formatDue(reminder.dueAt, hasTime: reminder.hasTime),
                        style: const TextStyle(
                            color: MC.muted, fontSize: 11)),
                    const SizedBox(width: 8),
                    Text(relativeDue(reminder.dueAt),
                        style: TextStyle(
                            color: overdue ? MC.red : MC.cyanDim,
                            fontSize: 11,
                            fontWeight: FontWeight.bold)),
                  ],
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.check_circle_outline),
            color: MC.green,
            onPressed: () => _complete(context),
          ),
          GestureDetector(
            onTap: () => _menu(context),
            child: const Padding(
              padding: EdgeInsets.all(4),
              child: Icon(Icons.more_vert, color: MC.muted, size: 18),
            ),
          ),
        ],
      ),
    );
  }
}
