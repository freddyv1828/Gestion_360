import 'package:flutter/material.dart';
import '../models/delivery_route.dart';
import '../models/user_profile.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../theme/app_theme.dart';
import '../widgets/app_states.dart';
import 'login_screen.dart';
import 'route_detail_screen.dart';

class RoutesScreen extends StatefulWidget {
  final UserProfile user;
  final AuthService authService;

  const RoutesScreen({super.key, required this.user, required this.authService});

  @override
  State<RoutesScreen> createState() => _RoutesScreenState();
}

class _RoutesScreenState extends State<RoutesScreen> {
  late Future<List<DeliveryRoute>> _routesFuture;

  @override
  void initState() {
    super.initState();
    _routesFuture = _load();
  }

  Future<List<DeliveryRoute>> _load() async {
    final raw = await ApiService.fetchMyRoutes();
    return raw.map((r) => DeliveryRoute.fromJson(r)).toList();
  }

  void _refresh() {
    setState(() => _routesFuture = _load());
  }

  void _logout() {
    widget.authService.signOut();
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Hola, ${widget.user.name.split(' ').first}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Cerrar sesión',
            onPressed: _logout,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => _refresh(),
        child: FutureBuilder<List<DeliveryRoute>>(
          future: _routesFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const AppLoading(message: 'Cargando tus rutas asignadas...');
            }
            if (snapshot.hasError) {
              return AppErrorState(message: snapshot.error.toString(), onRetry: _refresh);
            }
            final routes = snapshot.data ?? [];
            if (routes.isEmpty) {
              return ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: const [
                  SizedBox(height: 120),
                  AppEmptyState(
                    icon: Icons.local_shipping_outlined,
                    title: 'No tienes rutas asignadas',
                    subtitle: 'Cuando oficina te asigne una hoja de despacho, aparecerá aquí.',
                  ),
                ],
              );
            }
            return ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              itemCount: routes.length,
              separatorBuilder: (_, _) => const SizedBox(height: 12),
              itemBuilder: (context, index) => _RouteCard(
                route: routes[index],
                onTap: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => RouteDetailScreen(routeId: routes[index].id)),
                  );
                  _refresh();
                },
              ),
            );
          },
        ),
      ),
    );
  }
}

class _RouteCard extends StatelessWidget {
  final DeliveryRoute route;
  final VoidCallback onTap;

  const _RouteCard({required this.route, required this.onTap});

  static const _statusLabels = {
    'planificada': 'Planificada',
    'en_curso': 'En curso',
    'completada': 'Completada',
    'cancelada': 'Cancelada',
  };

  static const _statusColors = {
    'planificada': AppColors.muted,
    'en_curso': AppColors.amber,
    'completada': AppColors.green,
    'cancelada': AppColors.rose,
  };

  @override
  Widget build(BuildContext context) {
    final statusColor = _statusColors[route.status] ?? AppColors.muted;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                alignment: Alignment.center,
                child: Icon(Icons.local_shipping, color: statusColor),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(route.routeCode, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(route.destination, style: const TextStyle(color: AppColors.muted, fontSize: 13)),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: statusColor.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            _statusLabels[route.status] ?? route.status,
                            style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.w800),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '${route.deliveredCount}/${route.stopCount} entregadas',
                          style: const TextStyle(color: AppColors.muted, fontSize: 11, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: AppColors.mutedLight),
            ],
          ),
        ),
      ),
    );
  }
}
