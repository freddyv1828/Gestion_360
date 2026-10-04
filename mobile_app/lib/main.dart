import 'package:flutter/material.dart';

import 'screens/auth_screen.dart';
import 'screens/home_catalog_screen.dart';

void main() {
  runApp(const Gestion360App());
}

class Gestion360App extends StatelessWidget {
  const Gestion360App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Gestión 360 - Vitrina & Fuerza de Ventas',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF10B981)),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
      ),
      // Arranca en la vitrina pública (Guest Browsing); el login es opcional
      // hasta que el usuario decida comprar o es un vendedor corporativo.
      initialRoute: '/',
      routes: {
        '/': (context) => const HomeCatalogScreen(),
        '/auth': (context) => const AuthScreen(),
      },
    );
  }
}
