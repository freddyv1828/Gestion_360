// lib/web_main.dart
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

// Importamos pantallas del Backoffice Web
import 'admin/screens/portal_screen.dart';
import 'admin/screens/admin_dashboard_screen.dart';
import 'admin/screens/seller_management_screen.dart';
import 'screens/auth_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const Gestion360WebAdmin());
}

class Gestion360WebAdmin extends StatelessWidget {
  const Gestion360WebAdmin({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Gestión 360 - Backoffice Gerencial',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF10B981)),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
      ),
      // Arranca limpiamente en la portada corporativa, no en el dashboard
      initialRoute: '/',
      routes: {
        '/': (context) => const PortalScreen(),
        '/auth': (context) => const AuthScreen(),
        '/admin-dashboard': (context) => const AdminDashboardScreen(),
        '/seller-management': (context) => const SellerManagementScreen(),
      },
    );
  }
}