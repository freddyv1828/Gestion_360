import 'dart:async';
import 'package:flutter/material.dart';
import '../models/account_receivable.dart';
import '../models/seller_client.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/app_states.dart';

/// Directorio de clientes del vendedor: búsqueda en vivo contra el backend
/// (nunca trae el directorio completo de una vez) con paginación real y el
/// saldo pendiente de cada cliente a la vista.
class SellerClientsScreen extends StatefulWidget {
  const SellerClientsScreen({super.key});

  @override
  State<SellerClientsScreen> createState() => _SellerClientsScreenState();
}

class _SellerClientsScreenState extends State<SellerClientsScreen> {
  static const _perPage = 20;

  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  Timer? _debounce;

  final List<SellerClient> _clients = [];
  Map<String, double> _balanceByClientId = {};
  Map<String, double> _balanceByRif = {};

  String _query = '';
  int _page = 1;
  int _totalPages = 1;
  bool _isLoading = true;
  bool _isLoadingMore = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _loadReceivables();
    _load(reset: true);
    _scrollController.addListener(_onScroll);
  }

  // ignore: unused_element
  Future<void> reload() async {
    await _loadReceivables();
    await _load(reset: true);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadReceivables() async {
    try {
      final raw = await ApiService.fetchAccountsReceivable();
      final receivables = raw.map((r) => AccountReceivable.fromJson(r)).toList();
      if (!mounted) return;
      setState(() {
        _balanceByClientId = {
          for (final r in receivables)
            if (r.clientId != null) r.clientId!: r.balanceDue,
        };
        _balanceByRif = {for (final r in receivables) r.clientRif: r.balanceDue};
      });
    } catch (_) {
      // El directorio funciona igual sin el dato de saldo; no es bloqueante.
    }
  }

  void _onScroll() {
    if (_isLoadingMore || _page >= _totalPages) return;
    if (_scrollController.position.pixels > _scrollController.position.maxScrollExtent - 200) {
      _loadMore();
    }
  }

  void _onQueryChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      _query = value.trim();
      _load(reset: true);
    });
  }

  Future<void> _load({bool reset = false}) async {
    setState(() {
      _isLoading = true;
      _error = '';
      if (reset) {
        _page = 1;
        _clients.clear();
      }
    });
    try {
      final data = await ApiService.fetchSellerClientsPage(search: _query, limit: _perPage, page: _page);
      final raw = List<Map<String, dynamic>>.from(data['clients'] ?? []);
      if (!mounted) return;
      setState(() {
        _clients.addAll(raw.map((c) => SellerClient.fromJson(c)));
        _totalPages = (data['total_pages'] as num?)?.toInt() ?? 1;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _loadMore() async {
    setState(() => _isLoadingMore = true);
    _page += 1;
    try {
      final data = await ApiService.fetchSellerClientsPage(search: _query, limit: _perPage, page: _page);
      final raw = List<Map<String, dynamic>>.from(data['clients'] ?? []);
      if (!mounted) return;
      setState(() {
        _clients.addAll(raw.map((c) => SellerClient.fromJson(c)));
        _totalPages = (data['total_pages'] as num?)?.toInt() ?? 1;
      });
    } catch (_) {
      _page -= 1;
    } finally {
      if (mounted) setState(() => _isLoadingMore = false);
    }
  }

  double? _balanceFor(SellerClient c) {
    return _balanceByClientId[c.id] ?? _balanceByRif[c.rifCedula];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                labelText: 'Buscar por nombre, RIF/Cédula o correo',
                prefixIcon: Icon(Icons.search, size: 20),
              ),
              onChanged: _onQueryChanged,
            ),
          ),
          Expanded(
            child: _isLoading && _clients.isEmpty
                ? const AppLoading(message: 'Cargando clientes…')
                : _error.isNotEmpty && _clients.isEmpty
                    ? AppErrorState(message: _error, onRetry: () => _load(reset: true))
                    : _clients.isEmpty
                        ? const AppEmptyState(
                            icon: Icons.groups_outlined,
                            title: 'Sin clientes para mostrar',
                            subtitle: 'Prueba con otro nombre, RIF o correo.',
                          )
                        : RefreshIndicator(
                            onRefresh: () => _load(reset: true),
                            child: ListView.separated(
                              controller: _scrollController,
                              padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                              itemCount: _clients.length + (_page < _totalPages ? 1 : 0),
                              separatorBuilder: (ctx, i) => const SizedBox(height: 10),
                              itemBuilder: (ctx, i) {
                                if (i >= _clients.length) {
                                  return const Padding(
                                    padding: EdgeInsets.symmetric(vertical: 16),
                                    child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
                                  );
                                }
                                return _ClientCard(client: _clients[i], balanceDue: _balanceFor(_clients[i]));
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}

class _ClientCard extends StatelessWidget {
  final SellerClient client;
  final double? balanceDue;

  const _ClientCard({required this.client, this.balanceDue});

  @override
  Widget build(BuildContext context) {
    final isFiscal = client.clientType == 'fiscal';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    client.name,
                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14, color: AppColors.dark),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: (isFiscal ? AppColors.indigo : AppColors.green).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    isFiscal ? 'FISCAL' : 'NATURAL',
                    style: TextStyle(
                      color: isFiscal ? AppColors.indigo : AppColors.greenDark,
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(client.rifCedula, style: const TextStyle(color: AppColors.muted, fontSize: 12, fontFamily: 'monospace')),
            if (client.email.isNotEmpty || client.phone.isNotEmpty) ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  if (client.email.isNotEmpty) ...[
                    const Icon(Icons.email_outlined, size: 13, color: AppColors.muted),
                    const SizedBox(width: 4),
                    Flexible(child: Text(client.email, style: const TextStyle(fontSize: 11, color: AppColors.muted), overflow: TextOverflow.ellipsis)),
                  ],
                  if (client.email.isNotEmpty && client.phone.isNotEmpty) const SizedBox(width: 10),
                  if (client.phone.isNotEmpty) ...[
                    const Icon(Icons.phone_outlined, size: 13, color: AppColors.muted),
                    const SizedBox(width: 4),
                    Text(client.phone, style: const TextStyle(fontSize: 11, color: AppColors.muted)),
                  ],
                ],
              ),
            ],
            if (balanceDue != null && balanceDue! > 0) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.rose.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'Saldo pendiente: \$${balanceDue!.toStringAsFixed(2)}',
                  style: const TextStyle(color: AppColors.rose, fontSize: 11, fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
