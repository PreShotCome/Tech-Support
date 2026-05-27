import 'package:flutter/material.dart';
import '../models/reminder.dart';
import '../services/reminder_repository.dart';
import '../theme.dart';
import '../widgets/common.dart';

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('HISTORY')),
      body: ListenableBuilder(
        listenable: reminders,
        builder: (context, _) {
          final past = reminders.history;
          if (past.isEmpty) {
            return const EmptyState(
              icon: Icons.history,
              title: 'No history yet',
              subtitle:
                  'Completed and dismissed reminders are archived here.',
            );
          }
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              SectionLabel('${past.length} archived'),
              for (final r in past)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _HistoryCard(reminder: r),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _HistoryCard extends StatelessWidget {
  final Reminder reminder;
  const _HistoryCard({required this.reminder});

  @override
  Widget build(BuildContext context) {
    final done = reminder.status == ReminderStatus.completed;
    return MCard(
      onTap: () => _menu(context),
      child: Row(
        children: [
          Icon(done ? Icons.check_circle : Icons.cancel,
              color: done ? MC.green : MC.muted, size: 16),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(reminder.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        color: MC.text,
                        fontSize: 14,
                        decoration: done ? TextDecoration.lineThrough : null,
                        decorationColor: MC.muted)),
                const SizedBox(height: 4),
                Text(formatDue(reminder.dueAt, hasTime: reminder.hasTime),
                    style: const TextStyle(color: MC.muted, fontSize: 11)),
              ],
            ),
          ),
          Pill(done ? 'DONE' : 'DISMISSED',
              color: done ? MC.green : MC.muted),
        ],
      ),
    );
  }

  void _menu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: MC.surface,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.restore, color: MC.cyan, size: 20),
              title: const Text('Restore to pending',
                  style: TextStyle(color: MC.text, fontSize: 14)),
              onTap: () {
                Navigator.pop(ctx);
                reminders.setStatus(reminder, ReminderStatus.pending);
              },
            ),
            ListTile(
              leading:
                  const Icon(Icons.delete_outline, color: MC.red, size: 20),
              title: const Text('Delete permanently',
                  style: TextStyle(color: MC.red, fontSize: 14)),
              onTap: () {
                Navigator.pop(ctx);
                reminders.delete(reminder);
              },
            ),
          ],
        ),
      ),
    );
  }
}
