import 'package:flutter/material.dart';
import '../models/account_receivable.dart';
import '../services/api_service.dart';
import '../widgets/status_badge.dart';
import '../widgets/app_states.dart';
import '../theme/app_theme.dart';

const _kDark = AppColors.dark;
const _kGreen = AppColors.green;
const _kBlue = AppColors.blue;

class SellerDashboardTab extends StatefulWidget {
  const SellerDashboardTab({super.key});

  @override
  State<SellerDashboardTab> createState() => _SellerDashboardTabState();
}

class _SellerDashboardTabState extends State<SellerDashboardTab> {
  DashboardSummary? _summary;
  bool _isLoading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _isLoading = true;
      _error = '';
    });
    try {
      final raw = await ApiService.fetchSellerDashboard();
      setState(() => _summary = DashboardSummary.fromJson(raw));
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) return const AppLoading(message: 'Cargando tu panel…');
    if (_error.isNotEmpty) {
      return AppErrorState(message: _error, onRetry: _load);
    }
    final summary = _summary;
    if (summary == null) return const SizedBox();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: _SummaryCard(
                  icon: Icons.groups,
                  label: 'Clientes',
                  value: '${summary.clientsCount}',
                  color: _kBlue,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _SummaryCard(
                  icon: Icons.inbox,
                  label: 'Pedidos Abiertos',
                  value: '${summary.openOrdersCount}',
                  color: Colors.amber.shade700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _SummaryCard(
            icon: Icons.account_balance_wallet,
            label: 'Cuentas por Cobrar',
            value: '\$${summary.accountsReceivableTotal.toStringAsFixed(2)}',
            color: _kGreen,
            wide: true,
          ),
          const SizedBox(height: 20),
          const Text('Clientes con Mayor Saldo Pendiente',
              style: TextStyle(fontWeight: FontWeight.bold, color: _kDark)),
          const SizedBox(height: 8),
          if (summary.accountsReceivableTop.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Sin cuentas por cobrar pendientes.', style: TextStyle(color: Colors.grey, fontSize: 12)),
            )
          else
            ...summary.accountsReceivableTop.map((r) => _ReceivableTile(receivable: r)),
          const SizedBox(height: 20),
          const Text('Pedidos Recientes', style: TextStyle(fontWeight: FontWeight.bold, color: _kDark)),
          const SizedBox(height: 8),
          if (summary.recentOrders.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Sin pedidos registrados todavía.', style: TextStyle(color: Colors.grey, fontSize: 12)),
            )
          else
            ...summary.recentOrders.map((o) => Card(
                  elevation: 0,
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(color: Colors.grey.shade200),
                  ),
                  child: ListTile(
                    title: Text(o['order_number']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.bold)),
                    subtitle: Text(o['client_name']?.toString() ?? ''),
                    trailing: StatusBadge(status: o['status']?.toString() ?? 'pendiente'),
                  ),
                )),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final bool wide;

  const _SummaryCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
    this.wide = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: wide ? double.infinity : null,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
                Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: _kDark)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ReceivableTile extends StatelessWidget {
  final AccountReceivable receivable;
  const _ReceivableTile({required this.receivable});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: ListTile(
        title: Text(receivable.clientName, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text(receivable.clientRif),
        trailing: Text(
          '\$${receivable.balanceDue.toStringAsFixed(2)}',
          style: const TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }
}
