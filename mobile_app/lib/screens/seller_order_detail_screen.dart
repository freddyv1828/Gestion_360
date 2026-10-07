import 'package:flutter/material.dart';
import '../models/seller_order.dart';
import '../services/api_service.dart';
import '../widgets/status_badge.dart';
import '../widgets/app_states.dart';
import '../theme/app_theme.dart';

const _kDark = AppColors.dark;
const _kGreen = AppColors.green;

class SellerOrderDetailScreen extends StatefulWidget {
  final String orderId;
  const SellerOrderDetailScreen({super.key, required this.orderId});

  @override
  State<SellerOrderDetailScreen> createState() => _SellerOrderDetailScreenState();
}

class _SellerOrderDetailScreenState extends State<SellerOrderDetailScreen> {
  SellerOrder? _order;
  bool _isLoading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _isLoading = true);
    try {
      final raw = await ApiService.fetchOrderDetail(widget.orderId);
      setState(() => _order = SellerOrder.fromJson(raw));
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _cancelOrder() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('¿Anular este pedido?'),
        content: const Text('La mercancía bloqueada se liberará y volverá a estar disponible.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('No')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Sí, anular')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ApiService.cancelOrder(widget.orderId, reason: 'Anulado desde la app móvil');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Pedido anulado y stock liberado.')),
        );
      }
      _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_order?.orderNumber ?? 'Pedido'),
      ),
      body: _isLoading
          ? const AppLoading(message: 'Cargando pedido…')
          : _error.isNotEmpty
              ? AppErrorState(message: _error, onRetry: _load)
              : _order == null
                  ? const SizedBox()
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          Card(
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                              side: BorderSide(color: Colors.grey.shade200),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      StatusBadge(status: _order!.status),
                                      Text(
                                        _order!.docType == 'nota_entrega' ? 'Nota de Entrega' : 'Factura Fiscal',
                                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: _kDark),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 10),
                                  Text(_order!.clientName, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                                  Text(_order!.clientRif, style: const TextStyle(color: Colors.grey, fontSize: 12)),
                                  if (_order!.comment.isNotEmpty) ...[
                                    const SizedBox(height: 8),
                                    Text('Comentario: ${_order!.comment}', style: const TextStyle(fontSize: 12)),
                                  ],
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          const Text('Artículos', style: TextStyle(fontWeight: FontWeight.bold, color: _kDark)),
                          const SizedBox(height: 8),
                          ..._order!.items.map((item) => Card(
                                elevation: 0,
                                margin: const EdgeInsets.only(bottom: 8),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                  side: BorderSide(color: Colors.grey.shade200),
                                ),
                                child: ListTile(
                                  title: Text(item.name),
                                  subtitle: Text('${item.sku} · ${item.quantity} ${item.unitType}'),
                                  trailing: item.requiresWeighing
                                      ? Icon(
                                          item.verified ? Icons.check_circle : Icons.scale,
                                          color: item.verified ? _kGreen : Colors.amber.shade700,
                                        )
                                      : null,
                                ),
                              )),
                          const SizedBox(height: 20),
                          if (_order!.status != 'facturado' && _order!.status != 'anulado')
                            SizedBox(
                              width: double.infinity,
                              child: OutlinedButton.icon(
                                onPressed: _cancelOrder,
                                icon: const Icon(Icons.block, color: Colors.redAccent),
                                label: const Text('Anular Pedido', style: TextStyle(color: Colors.redAccent)),
                                style: OutlinedButton.styleFrom(side: const BorderSide(color: Colors.redAccent)),
                              ),
                            ),
                        ],
                      ),
                    ),
    );
  }
}
