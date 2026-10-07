import 'package:flutter/material.dart';

/// Paleta de marca única para toda la app — mismos tonos que el panel web
/// (templates/base.html) para que vendedor y oficina vean el mismo lenguaje
/// visual. Centralizada aquí para no repetir `Color(0xFF...)` en cada pantalla.
class AppColors {
  AppColors._();

  static const dark = Color(0xFF0F172A); // slate-900
  static const darkSurface = Color(0xFF1E293B); // slate-800
  static const green = Color(0xFF10B981); // emerald-500
  static const greenDark = Color(0xFF059669); // emerald-600
  static const bg = Color(0xFFF8FAFC); // slate-50
  static const card = Colors.white;
  static const border = Color(0xFFE2E8F0); // slate-200
  static const muted = Color(0xFF64748B); // slate-500
  static const mutedLight = Color(0xFF94A3B8); // slate-400

  static const blue = Color(0xFF38BDF8);
  static const indigo = Color(0xFF4F46E5);
  static const amber = Color(0xFFD97706);
  static const rose = Color(0xFFE11D48);
}

class AppTheme {
  AppTheme._();

  static ThemeData get light {
    final base = ColorScheme.fromSeed(
      seedColor: AppColors.green,
      brightness: Brightness.light,
    );
    final colorScheme = base.copyWith(
      primary: AppColors.green,
      onPrimary: Colors.white,
      secondary: AppColors.dark,
      surface: AppColors.card,
      error: AppColors.rose,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AppColors.bg,
      splashFactory: InkRipple.splashFactory,
      fontFamily: 'Roboto',

      textTheme: const TextTheme(
        headlineSmall: TextStyle(fontWeight: FontWeight.w800, color: AppColors.dark, letterSpacing: -0.3),
        titleLarge: TextStyle(fontWeight: FontWeight.w800, color: AppColors.dark, letterSpacing: -0.2),
        titleMedium: TextStyle(fontWeight: FontWeight.w700, color: AppColors.dark),
        titleSmall: TextStyle(fontWeight: FontWeight.w700, color: AppColors.dark),
        bodyLarge: TextStyle(color: AppColors.dark),
        bodyMedium: TextStyle(color: AppColors.dark),
        labelLarge: TextStyle(fontWeight: FontWeight.w700),
        labelSmall: TextStyle(color: AppColors.muted, fontWeight: FontWeight.w600),
      ),

      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.dark,
        foregroundColor: Colors.white,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleTextStyle: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w800),
      ),

      cardTheme: CardThemeData(
        color: AppColors.card,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.border),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.bg,
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        labelStyle: const TextStyle(color: AppColors.muted, fontSize: 13),
        hintStyle: TextStyle(color: AppColors.mutedLight.withValues(alpha: 0.8), fontSize: 13),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.green, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.rose),
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.green,
          foregroundColor: Colors.white,
          disabledBackgroundColor: AppColors.green.withValues(alpha: 0.4),
          elevation: 0,
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.dark,
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
          textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
          side: const BorderSide(color: AppColors.border),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),

      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.green,
          textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),

      chipTheme: ChipThemeData(
        backgroundColor: AppColors.bg,
        selectedColor: AppColors.green,
        disabledColor: AppColors.border,
        labelStyle: const TextStyle(fontSize: 12, color: AppColors.dark, fontWeight: FontWeight.w600),
        secondaryLabelStyle: const TextStyle(fontSize: 12, color: Colors.white, fontWeight: FontWeight.w700),
        side: const BorderSide(color: AppColors.border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      ),

      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        indicatorColor: AppColors.green.withValues(alpha: 0.14),
        height: 66,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return TextStyle(
            fontSize: 11,
            fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
            color: selected ? AppColors.greenDark : AppColors.muted,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return IconThemeData(color: selected ? AppColors.greenDark : AppColors.muted, size: 22);
        }),
      ),

      dividerTheme: const DividerThemeData(color: AppColors.border, thickness: 1, space: 1),

      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.dark,
        contentTextStyle: const TextStyle(color: Colors.white, fontSize: 13),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),

      progressIndicatorTheme: const ProgressIndicatorThemeData(color: AppColors.green),

      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: AppColors.green,
        foregroundColor: Colors.white,
        elevation: 1,
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        titleTextStyle: const TextStyle(color: AppColors.dark, fontSize: 16, fontWeight: FontWeight.w800),
        contentTextStyle: const TextStyle(color: AppColors.muted, fontSize: 13),
      ),

      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
        showDragHandle: true,
      ),
    );
  }
}
