import 'dart:math';
import 'package:flutter/material.dart';

class StarField extends StatefulWidget {
  final Widget child;
  const StarField({super.key, required this.child});
  @override
  State<StarField> createState() => _StarFieldState();
}

class _StarFieldState extends State<StarField> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  final _stars = <_Star>[];
  final _rng = Random();

  @override
  void initState() {
    super.initState();
    for (int i = 0; i < 120; i++) {
      _stars.add(_Star(
        x: _rng.nextDouble(),
        y: _rng.nextDouble(),
        size: _rng.nextDouble() * 2.0 + 0.5,
        speed: _rng.nextDouble() * 0.0002 + 0.00005,
        opacity: _rng.nextDouble() * 0.7 + 0.3,
      ));
    }
    _controller = AnimationController(vsync: this, duration: const Duration(seconds: 60))
      ..repeat();
  }

  @override
  void dispose() { _controller.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        for (final s in _stars) {
          s.y -= s.speed;
          if (s.y < 0) { s.y = 1.0; s.x = _rng.nextDouble(); }
        }
        return CustomPaint(
          painter: _StarPainter(_stars),
          child: widget.child,
        );
      },
    );
  }
}

class _Star {
  double x, y, size, speed, opacity;
  _Star({required this.x, required this.y, required this.size,
         required this.speed, required this.opacity});
}

class _StarPainter extends CustomPainter {
  final List<_Star> stars;
  _StarPainter(this.stars);

  @override
  void paint(Canvas canvas, Size size) {
    for (final s in stars) {
      final paint = Paint()
        ..color = Colors.white.withOpacity(s.opacity)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(Offset(s.x * size.width, s.y * size.height), s.size, paint);
    }
  }

  @override
  bool shouldRepaint(_StarPainter old) => true;
}
