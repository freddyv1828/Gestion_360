import 'dart:async';
import 'package:flutter/material.dart';
import '../models/seller_product.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/app_states.dart';

/// Catálogo de artículos para consulta del vendedor (precio, stock por
/// almacén) sin necesidad de abrir un Pedido. Busca y pagina contra el
/// backend — nunca precarga el catálogo completo.
class SellerCatalogScreen extends StatefulWidget {
  const SellerCatalogScreen({super.key});

  @override
  State<SellerCatalogScreen> createState() => _SellerCatalogScreenState();
}

class _SellerCatalogScreenState extends State<SellerCatalogScreen> {
  static const _perPage = 20;

  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  Timer? _debounce;

  List<SellerWarehouse> _warehouses = [];
  String? _warehouseId;

  final List<SellerProduct> _products = [];
  String _query = '';
  int _page = 1;
  int _totalPages = 1;
  bool _isLoading = true;
  bool _isLoadingMore = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _loadWarehouses();
    _load(reset: true);
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadWarehouses() async {
    try {
      final raw = await ApiService.fetchWarehouses();
      if (!mounted) return;
      setState(() => _warehouses = raw.map((w) => SellerWarehouse.fromJson(w)).toList());
    } catch (_) {
      // El catálogo sigue siendo útil sin el filtro de almacén.
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

  void _onWarehouseChanged(String? value) {
    setState(() => _warehouseId = value);
    _load(reset: true);
  }

  Future<void> _load({bool reset = false}) async {
    setState(() {
      _isLoading = true;
      _error = '';
      if (reset) {
        _page = 1;
        _products.clear();
      }
    });
    try {
      final data = await ApiService.fetchSellerProducts(
        page: _page,
        perPage: _perPage,
        search: _query,
        warehouseId: _warehouseId ?? '',
      );
      final raw = List<Map<String, dynamic>>.from(data['products'] ?? []);
      if (!mounted) return;
      setState(() {
        _products.addAll(raw.map((p) => SellerProduct.fromJson(p)));
        _totalPages = (data['pagination']?['total_pages'] as num?)?.toInt() ?? 1;
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
      final data = await ApiService.fetchSellerProducts(
        page: _page,
        perPage: _perPage,
        search: _query,
        warehouseId: _warehouseId ?? '',
      );
      final raw = List<Map<String, dynamic>>.from(data['products'] ?? []);
      if (!mounted) return;
      setState(() {
        _products.addAll(raw.map((p) => SellerProduct.fromJson(p)));
        _totalPages = (data['pagination']?['total_pages'] as num?)?.toInt() ?? 1;
      });
    } catch (_) {
      _page -= 1;
    } finally {
      if (mounted) setState(() => _isLoadingMore = false);
    }
  }

  void _showDetail(SellerProduct product) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => _ProductDetailSheet(product: product, warehouses: _warehouses),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Row(
              children: [
                Expanded(
                  flex: 3,
                  child: TextField(
                    controller: _searchController,
                    decoration: const InputDecoration(
                      labelText: 'Buscar por nombre o SKU',
                      prefixIcon: Icon(Icons.search, size: 20),
                    ),
                    onChanged: _onQueryChanged,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  flex: 2,
                  child: DropdownButtonFormField<String>(
                    initialValue: _warehouseId,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Almacén'),
                    items: [
                      const DropdownMenuItem(value: null, child: Text('Todos', overflow: TextOverflow.ellipsis)),
                      ..._warehouses.map((w) => DropdownMenuItem(value: w.id, child: Text(w.name, overflow: TextOverflow.ellipsis))),
                    ],
                    onChanged: _onWarehouseChanged,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: _isLoading && _products.isEmpty
                ? const AppLoading(message: 'Cargando catálogo…')
                : _error.isNotEmpty && _products.isEmpty
                    ? AppErrorState(message: _error, onRetry: () => _load(reset: true))
                    : _products.isEmpty
                        ? const AppEmptyState(
                            icon: Icons.inventory_2_outlined,
                            title: 'Sin artículos para mostrar',
                            subtitle: 'Prueba con otro nombre, SKU o almacén.',
                          )
                        : RefreshIndicator(
                            onRefresh: () => _load(reset: true),
                            child: ListView.separated(
                              controller: _scrollController,
                              padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                              itemCount: _products.length + (_page < _totalPages ? 1 : 0),
                              separatorBuilder: (ctx, i) => const SizedBox(height: 10),
                              itemBuilder: (ctx, i) {
                                if (i >= _products.length) {
                                  return const Padding(
                                    padding: EdgeInsets.symmetric(vertical: 16),
                                    child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
                                  );
                                }
                                final p = _products[i];
                                final avail = _warehouseId != null ? p.availabilityFor(_warehouseId) : p.stock;
                                return Card(
                                  child: InkWell(
                                    borderRadius: BorderRadius.circular(16),
                                    onTap: () => _showDetail(p),
                                    child: Padding(
                                      padding: const EdgeInsets.all(10),
                                      child: Row(
                                        children: [
                                          _Thumb(url: p.imageUrl),
                                          const SizedBox(width: 12),
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                Text(p.name,
                                                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: AppColors.dark),
                                                    maxLines: 1,
                                                    overflow: TextOverflow.ellipsis),
                                                const SizedBox(height: 2),
                                                Text('SKU ${p.sku} · ${p.brand.isNotEmpty ? p.brand : p.category}',
                                                    style: const TextStyle(fontSize: 11, color: AppColors.muted)),
                                                const SizedBox(height: 4),
                                                Text(
                                                  'Disponible: ${avail.toStringAsFixed(2)} ${p.unitType}',
                                                  style: TextStyle(
                                                    fontSize: 11,
                                                    fontWeight: FontWeight.w700,
                                                    color: avail > 0 ? AppColors.greenDark : AppColors.rose,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                          Text('\$${p.price.toStringAsFixed(2)}',
                                              style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.dark, fontSize: 14)),
                                        ],
                                      ),
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}

class _Thumb extends StatelessWidget {
  final String? url;
  const _Thumb({this.url});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Container(
        width: 52,
        height: 52,
        color: AppColors.bg,
        child: url == null
            ? const Icon(Icons.inventory_2_outlined, color: AppColors.muted, size: 22)
            : Image.network(
                url!,
                fit: BoxFit.cover,
                loadingBuilder: (ctx, child, progress) {
                  if (progress == null) return child;
                  return const Center(child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)));
                },
                errorBuilder: (ctx, err, stack) => const Icon(Icons.inventory_2_outlined, color: AppColors.muted, size: 22),
              ),
      ),
    );
  }
}

class _ProductDetailSheet extends StatelessWidget {
  final SellerProduct product;
  final List<SellerWarehouse> warehouses;

  const _ProductDetailSheet({required this.product, required this.warehouses});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 8, 20, MediaQuery.of(context).viewInsets.bottom + 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _Thumb(url: product.imageUrl),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(product.name, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: AppColors.dark)),
                    Text('SKU ${product.sku}', style: const TextStyle(fontSize: 12, color: AppColors.muted)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _Stat(label: 'Precio', value: '\$${product.price.toStringAsFixed(2)}')),
              Expanded(child: _Stat(label: 'IVA', value: '${product.ivaRate.toStringAsFixed(0)}%')),
              Expanded(child: _Stat(label: 'Unidad', value: product.unitType)),
            ],
          ),
          const SizedBox(height: 16),
          const Text('Disponibilidad por almacén', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.dark, fontSize: 13)),
          const SizedBox(height: 8),
          if (warehouses.isEmpty)
            Text('Stock total: ${product.stock.toStringAsFixed(2)} ${product.unitType}', style: const TextStyle(color: AppColors.muted, fontSize: 12))
          else
            ...warehouses.map((w) {
              final qty = product.availabilityFor(w.id);
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(w.name, style: const TextStyle(fontSize: 12, color: AppColors.dark)),
                    Text(
                      '${qty.toStringAsFixed(2)} ${product.unitType}',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: qty > 0 ? AppColors.greenDark : AppColors.rose),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  const _Stat({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 10, color: AppColors.muted, fontWeight: FontWeight.w600)),
        Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: AppColors.dark)),
      ],
    );
  }
}
