import 'package:flutter/material.dart';
import '../models/delivery_route.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/app_states.dart';
import 'delivery_confirmation_screen.dart';

class RouteDetailScreen extends StatefulWidget {
  final String routeId;
  const RouteDetailScreen({super.key, required this.routeId});

  @override
  State<RouteDetailScreen> createState() => _RouteDetailScreenState();
}

class _RouteDetailScreenState extends State<RouteDetailScreen> {
  late Future<DeliveryRouteDetail> _detailFuture;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _detailFuture = _load();
  }

  Future<DeliveryRouteDetail> _load() async {
    final raw = await ApiService.fetchRouteDetail(widget.routeId);
    return DeliveryRouteDetail.fromJson(raw);
  }

  void _refresh() => setState(() => _detailFuture = _load());

  void _showMessage(String message, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? AppColors.rose : AppColors.green,
      ),
    );
  }

  Future<void> _startRoute() async {
    setState(() => _busy = true);
    try {
      final message = await ApiService.startRoute(widget.routeId);
      _showMessage(message);
      _refresh();
    } catch (e) {
      _showMessage(e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _completeRoute() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('¿Completar la ruta?'),
        content: const Text(
          'Cualquier parada que no hayas confirmado individualmente con foto y firma '
          'quedará marcada como entregada en este momento.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Completar')),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _busy = true);
    try {
      final message = await ApiService.completeRoute(widget.routeId);
      _showMessage(message);
      _refresh();
    } catch (e) {
      _showMessage(e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Hoja de Despacho')),
      body: FutureBuilder<DeliveryRouteDetail>(
        future: _detailFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const AppLoading(message: 'Cargando la ruta...');
          }
          if (snapshot.hasError) {
            return AppErrorState(message: snapshot.error.toString(), onRetry: _refresh);
          }
          final route = snapshot.data!;
          final allDelivered = route.stops.isNotEmpty && route.stops.every((s) => s.delivered);

          return Column(
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                color: AppColors.dark,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(route.routeCode,
                        style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800)),
                    const SizedBox(height: 2),
                    Text(route.destination, style: const TextStyle(color: Colors.white70, fontSize: 13)),
                    const SizedBox(height: 10),
                    Text(
                      '${route.stops.where((s) => s.delivered).length} de ${route.stops.length} paradas entregadas',
                      style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
              if (route.status == 'planificada')
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _busy ? null : _startRoute,
                      icon: const Icon(Icons.play_arrow),
                      label: const Text('Iniciar Ruta'),
                    ),
                  ),
                ),
              Expanded(
                child: route.stops.isEmpty
                    ? const AppEmptyState(icon: Icons.inbox_outlined, title: 'Esta ruta no tiene paradas cargadas')
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: route.stops.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 10),
                        itemBuilder: (context, index) {
                          final stop = route.stops[index];
                          return _StopCard(
                            stop: stop,
                            index: index + 1,
                            enabled: route.status == 'en_curso' && !stop.delivered,
                            onTap: () async {
                              await Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => DeliveryConfirmationScreen(stop: stop),
                                ),
                              );
                              _refresh();
                            },
                          );
                        },
                      ),
              ),
              if (route.status == 'en_curso')
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: _busy ? null : _completeRoute,
                      icon: Icon(allDelivered ? Icons.check_circle : Icons.flag_outlined),
                      label: Text(allDelivered ? 'Completar Ruta' : 'Completar Ruta (faltan paradas)'),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _StopCard extends StatelessWidget {
  final dynamic stop;
  final int index;
  final bool enabled;
  final VoidCallback onTap;

  const _StopCard({required this.stop, required this.index, required this.enabled, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: enabled ? onTap : null,
        child: Opacity(
          opacity: stop.delivered ? 0.6 : 1.0,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 16,
                  backgroundColor: stop.delivered ? AppColors.green.withValues(alpha: 0.15) : AppColors.amber.withValues(alpha: 0.15),
                  child: stop.delivered
                      ? const Icon(Icons.check, color: AppColors.green, size: 18)
                      : Text('$index', style: const TextStyle(color: AppColors.amberDark, fontWeight: FontWeight.w800)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(stop.clientName, style: Theme.of(context).textTheme.titleSmall),
                      if (stop.clientAddress.toString().isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(stop.clientAddress, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                        ),
                      const SizedBox(height: 4),
                      Text(
                        '${stop.invoiceNumber} · ${stop.total.toStringAsFixed(2)} ${stop.currency}',
                        style: const TextStyle(color: AppColors.muted, fontSize: 11, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
                if (stop.delivered)
                  const Text('Entregado', style: TextStyle(color: AppColors.green, fontSize: 11, fontWeight: FontWeight.w800))
                else if (enabled)
                  const Icon(Icons.chevron_right, color: AppColors.mutedLight),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
