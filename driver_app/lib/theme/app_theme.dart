import 'package:flutter/material.dart';

/// Misma familia de marca que la app del vendedor (mobile_app/lib/theme),
/// pero con acento ámbar en vez de verde — para que a simple vista se note
/// que esta es la app de Despacho/Entregas, no la de Ventas, aunque compartan
/// identidad visual y backend.
class AppColors {
  AppColors._();

  static const dark = Color(0xFF0F172A); // slate-900
  static const darkSurface = Color(0xFF1E293B); // slate-800
  static const amber = Color(0xFFD97706); // amber-600
  static const amberDark = Color(0xFFB45309); // amber-700
  static const bg = Color(0xFFF8FAFC); // slate-50
  static const card = Colors.white;
  static const border = Color(0xFFE2E8F0); // slate-200
  static const muted = Color(0xFF64748B); // slate-500
  static const mutedLight = Color(0xFF94A3B8); // slate-400

  static const green = Color(0xFF10B981); // emerald-500 (entregado)
  static const rose = Color(0xFFE11D48); // rose-600 (error/cancelado)
  static const indigo = Color(0xFF4F46E5); // indigo-600
}

class AppTheme {
  AppTheme._();

  static ThemeData get light {
    final base = ColorScheme.fromSeed(
      seedColor: AppColors.amber,
      brightness: Brightness.light,
    );
    final colorScheme = base.copyWith(
      primary: AppColors.amber,
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
        centerTitle: false,
        elevation: 0,
        titleTextStyle: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 18),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.bg,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
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
          borderSide: const BorderSide(color: AppColors.amber, width: 1.6),
        ),
        labelStyle: const TextStyle(color: AppColors.muted, fontSize: 13),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.amber,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.dark,
          side: const BorderSide(color: AppColors.border),
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),

      cardTheme: CardThemeData(
        color: AppColors.card,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.border),
        ),
        margin: EdgeInsets.zero,
      ),

      dividerTheme: const DividerThemeData(color: AppColors.border, thickness: 1),
    );
  }
}
