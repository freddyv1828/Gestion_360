import 'package:flutter/material.dart';
import '../models/user_profile.dart';
import '../services/auth_service.dart';
import '../theme/app_theme.dart';
import '../widgets/brand_mark.dart';
import 'seller_budgets_screen.dart';
import 'seller_catalog_screen.dart';
import 'seller_clients_screen.dart';
import 'seller_dashboard_tab.dart';
import 'seller_orders_screen.dart';
import 'seller_receivables_screen.dart';

/// Shell principal de la App Móvil del Vendedor: Dashboard, Pedidos,
/// Presupuestos, Clientes, Cobros y Catálogo, con la misma paleta de marca
/// que el panel web.
class SellerHomeScreen extends StatefulWidget {
  final UserProfile user;
  final AuthService authService;

  const SellerHomeScreen({super.key, required this.user, required this.authService});

  @override
  State<SellerHomeScreen> createState() => _SellerHomeScreenState();
}

class _SellerHomeScreenState extends State<SellerHomeScreen> {
  int _tabIndex = 0;

  static const _titles = ['Dashboard', 'Pedidos', 'Presupuestos', 'Clientes', 'Cobros', 'Catálogo'];

  List<Widget> get _tabs => const [
        SellerDashboardTab(),
        SellerOrdersScreen(),
        SellerBudgetsScreen(),
        SellerClientsScreen(),
        SellerReceivablesScreen(),
        SellerCatalogScreen(),
      ];

  Future<void> _confirmLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('¿Cerrar sesión?'),
        content: const Text('Tendrás que volver a ingresar tus credenciales para continuar.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Cerrar sesión')),
        ],
      ),
    );
    if (confirmed != true) return;
    widget.authService.signOut();
    if (mounted) Navigator.pushNamedAndRemoveUntil(context, '/auth', (route) => false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const BrandMark(size: 32, background: Colors.white10),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_titles[_tabIndex], style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w800)),
                  Text(
                    widget.user.businessName ?? 'Gestión 360',
                    style: const TextStyle(color: AppColors.mutedLight, fontSize: 11),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white, size: 20),
            onPressed: _confirmLogout,
            tooltip: 'Cerrar Sesión',
          ),
        ],
      ),
      body: IndexedStack(index: _tabIndex, children: _tabs),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tabIndex,
        onDestinationSelected: (i) => setState(() => _tabIndex = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard), label: 'Dashboard'),
          NavigationDestination(icon: Icon(Icons.inbox_outlined), selectedIcon: Icon(Icons.inbox), label: 'Pedidos'),
          NavigationDestination(icon: Icon(Icons.request_quote_outlined), selectedIcon: Icon(Icons.request_quote), label: 'Presupuestos'),
          NavigationDestination(icon: Icon(Icons.groups_outlined), selectedIcon: Icon(Icons.groups), label: 'Clientes'),
          NavigationDestination(icon: Icon(Icons.payments_outlined), selectedIcon: Icon(Icons.payments), label: 'Cobros'),
          NavigationDestination(icon: Icon(Icons.inventory_2_outlined), selectedIcon: Icon(Icons.inventory_2), label: 'Catálogo'),
        ],
      ),
    );
  }
}
