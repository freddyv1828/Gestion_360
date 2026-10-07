import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Monograma de marca reutilizable (AppBar, login, estados de carga) para que
/// la app se sienta identificada en vez de usar iconos genéricos de Material.
class BrandMark extends StatelessWidget {
  final double size;
  final Color background;
  final Color foreground;

  const BrandMark({
    super.key,
    this.size = 40,
    this.background = AppColors.dark,
    this.foreground = AppColors.green,
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
