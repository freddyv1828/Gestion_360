import 'package:flutter/material.dart';
import '../models/user_profile.dart';
import '../services/auth_service.dart';
import 'seller_budgets_screen.dart';
import 'seller_clients_screen.dart';
import 'seller_dashboard_tab.dart';
import 'seller_orders_screen.dart';

const _kDark = Color(0xFF0F172A);
const _kGreen = Color(0xFF10B981);
const _kBg = Color(0xFFF8FAFC);

/// Shell principal de la App Móvil del Vendedor: Dashboard, Pedidos,
/// Presupuestos y Clientes, con la misma paleta de marca que el panel web.
class SellerHomeScreen extends StatefulWidget {
  final UserProfile user;
  final AuthService authService;

  const SellerHomeScreen({super.key, required this.user, required this.authService});

  @override
  State<SellerHomeScreen> createState() => _SellerHomeScreenState();
}

class _SellerHomeScreenState extends State<SellerHomeScreen> {
  int _tabIndex = 0;

  static const _titles = ['Dashboard', 'Pedidos', 'Presupuestos', 'Clientes'];

  List<Widget> get _tabs => const [
        SellerDashboardTab(),
        SellerOrdersScreen(),
        SellerBudgetsScreen(),
        SellerClientsScreen(),
      ];

  void _logout() {
    widget.authService.signOut();
    Navigator.pushNamedAndRemoveUntil(context, '/auth', (route) => false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBg,
      appBar: AppBar(
        backgroundColor: _kDark,
        elevation: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_titles[_tabIndex], style: const TextStyle(color: Colors.white, fontSize: 16)),
            Text(
              widget.user.businessName ?? 'Gestión 360',
              style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white),
            onPressed: _logout,
            tooltip: 'Cerrar Sesión',
          ),
        ],
      ),
      body: IndexedStack(index: _tabIndex, children: _tabs),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _tabIndex,
        onTap: (i) => setState(() => _tabIndex = i),
        selectedItemColor: _kGreen,
        unselectedItemColor: Colors.grey,
        type: BottomNavigationBarType.fixed,
        backgroundColor: Colors.white,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.inbox_outlined), label: 'Pedidos'),
          BottomNavigationBarItem(icon: Icon(Icons.request_quote_outlined), label: 'Presupuestos'),
          BottomNavigationBarItem(icon: Icon(Icons.groups_outlined), label: 'Clientes'),
        ],
      ),
    );
  }
}
