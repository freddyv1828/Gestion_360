import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Mismo monograma que la app del vendedor, pero con acento ámbar — marca
/// compartida, identidad de app distinta.
class BrandMark extends StatelessWidget {
  final double size;
  final Color background;
  final Color foreground;

  const BrandMark({
    super.key,
    this.size = 40,
    this.background = AppColors.dark,
    this.foreground = AppColors.amber,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(size * 0.28),
        border: Border.all(color: foreground.withValues(alpha: 0.5), width: 1.4),
      ),
      alignment: Alignment.center,
      child: Text(
        'G360',
        style: TextStyle(
          color: foreground,
          fontWeight: FontWeight.w900,
          fontSize: size * 0.24,
          letterSpacing: -0.4,
        ),
      ),
    );
  }
}
