import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../theme.dart';

String formatDue(DateTime dt, {bool hasTime = true}) {
  final now = DateTime.now();
  final d = DateTime(dt.year, dt.month, dt.day);
  final today = DateTime(now.year, now.month, now.day);
  final diff = d.difference(today).inDays;
  final time = DateFormat('HH:mm').format(dt);
  final String dayLabel;
  if (diff == 0) {
    dayLabel = 'Today';
  } else if (diff == 1) {
    dayLabel = 'Tomorrow';
  } else if (diff == -1) {
    dayLabel = 'Yesterday';
  } else if (diff > 1 && diff < 7) {
    dayLabel = DateFormat('EEEE').format(dt);
  } else {
    dayLabel = DateFormat('MMM d').format(dt);
  }
  return hasTime ? '$dayLabel · $time' : dayLabel;
}

String relativeDue(DateTime dt) {
  final diff = dt.difference(DateTime.now());
  if (diff.isNegative) {
    final ago = diff.abs();
    if (ago.inMinutes < 60) return '${ago.inMinutes}m overdue';
    if (ago.inHours < 24) return '${ago.inHours}h overdue';
    return '${ago.inDays}d overdue';
  }
  if (diff.inMinutes < 1) return 'now';
  if (diff.inMinutes < 60) return 'in ${diff.inMinutes}m';
  if (diff.inHours < 24) return 'in ${diff.inHours}h';
  return 'in ${diff.inDays}d';
}

/// Standard dark card surface.
class MCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final Color? accent;
  const MCard({
    super.key,
    required this.child,
    this.onTap,
    this.accent,
    this.padding = const EdgeInsets.all(14),
  });

  @override
  Widget build(BuildContext context) {
    // IntrinsicHeight gives the row a defined height so the accent strip can
    // stretch to it; without it the stretch row collapses to zero height
    // inside a scroll view and the whole card becomes invisible.
    final Widget body = accent == null
        ? Padding(padding: padding, child: child)
        : IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(width: 3, color: accent),
                Expanded(child: Padding(padding: padding, child: child)),
              ],
            ),
          );

    final card = Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: MC.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: MC.border),
      ),
      child: body,
    );
    if (onTap == null) return card;
    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: onTap,
      child: card,
    );
  }
}

/// Uppercased, letter-spaced section header.
class SectionLabel extends StatelessWidget {
  final String text;
  final Widget? trailing;
  const SectionLabel(this.text, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 18, 4, 8),
        child: Row(
          children: [
            Text('// ${text.toUpperCase()}',
                style: const TextStyle(
                    color: MC.muted,
                    fontSize: 11,
                    letterSpacing: 2,
                    fontWeight: FontWeight.bold)),
            const Spacer(),
            if (trailing != null) trailing!,
          ],
        ),
      );
}

/// Centered empty-state placeholder.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: MC.card,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: MC.border),
                ),
                child: Icon(icon, color: MC.cyanDim, size: 28),
              ),
              const SizedBox(height: 14),
              Text(title,
                  style: const TextStyle(
                      color: MC.text,
                      fontSize: 14,
                      fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              Text(subtitle,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      color: MC.muted, fontSize: 12, height: 1.5)),
            ],
          ),
        ),
      );
}

/// Small pill used for counts and tags.
class Pill extends StatelessWidget {
  final String text;
  final Color color;
  const Pill(this.text, {super.key, this.color = MC.cyan});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: color.withOpacity(0.14),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(text,
            style: TextStyle(
                color: color, fontSize: 10, fontWeight: FontWeight.bold)),
      );
}
