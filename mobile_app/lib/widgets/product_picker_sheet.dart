import 'dart:async';
import 'package:flutter/material.dart';
import '../models/seller_product.dart';
import '../services/api_service.dart';

const _kGreen = Color(0xFF10B981);
const _kDark = Color(0xFF0F172A);

/// Imagen con placeholder — las URLs vienen de distintos orígenes (CDN del
/// catálogo de prueba, R2, etc.) y algunas pueden fallar o no existir.
class _ProductThumb extends StatelessWidget {
  final String? url;
  const _ProductThumb({this.url});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: 44,
        height: 44,
        color: const Color(0xFFF1F5F9),
        child: (url == null)
            ? const Icon(Icons.inventory_2_outlined, color: Colors.grey, size: 20)
            : Image.network(
                url!,
                fit: BoxFit.cover,
                loadingBuilder: (ctx, child, progress) {
                  if (progress == null) return child;
                  return const Center(child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)));
                },
                errorBuilder: (ctx, err, stack) => const Icon(Icons.inventory_2_outlined, color: Colors.grey, size: 20),
              ),
      ),
    );
  }
}

/// Bottom sheet de selección de artículos: busca y pagina contra el backend
/// en vez de precargar todo el catálogo. Muestra imagen, precio y
/// disponibilidad en el almacén elegido.
class ProductPickerSheet extends StatefulWidget {
  final String? warehouseId;
  const ProductPickerSheet({super.key, this.warehouseId});

  @override
  State<ProductPickerSheet> createState() => _ProductPickerSheetState();

  static Future<SellerProduct?> show(BuildContext context, {String? warehouseId}) {
    return showModalBottomSheet<SellerProduct>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => ProductPickerSheet(warehouseId: warehouseId),
    );
  }
}

class _ProductPickerSheetState extends State<ProductPickerSheet> {
  final _searchController = TextEditingController();
  Timer? _debounce;
  List<SellerProduct> _products = [];
  bool _loading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _search('');
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _search(String query) async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final data = await ApiService.fetchSellerProducts(search: query, perPage: 25, warehouseId: widget.warehouseId ?? '');
      final raw = List<Map<String, dynamic>>.from(data['products'] ?? []);
      setState(() => _products = raw.map((p) => SellerProduct.fromJson(p)).toList());
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _onQueryChanged(String query) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () => _search(query));
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (ctx, scrollController) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Agregar Artículo', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: _kDark)),
              const SizedBox(height: 12),
              TextField(
                controller: _searchController,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'Buscar por nombre o SKU',
                  prefixIcon: Icon(Icons.search, size: 20),
                ),
                onChanged: _onQueryChanged,
              ),
              const SizedBox(height: 10),
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : _error.isNotEmpty
                        ? Center(child: Text(_error, style: const TextStyle(color: Colors.red)))
                        : _products.isEmpty
                            ? const Center(child: Text('Sin resultados.', style: TextStyle(color: Colors.grey)))
                            : ListView.builder(
                                controller: scrollController,
                                itemCount: _products.length,
                                itemBuilder: (ctx, i) {
                                  final p = _products[i];
                                  final avail = widget.warehouseId != null ? p.availabilityFor(widget.warehouseId) : null;
                                  return ListTile(
                                    leading: _ProductThumb(url: p.imageUrl),
                                    title: Text(p.name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                                    subtitle: Text(
                                      'SKU ${p.sku} · \$${p.price.toStringAsFixed(2)}'
                                      '${avail != null ? ' · Disponible: ${avail.toStringAsFixed(2)}' : ''}',
                                      style: const TextStyle(fontSize: 11),
                                    ),
                                    trailing: const Icon(Icons.add_circle_outline, color: _kGreen),
                                    onTap: () => Navigator.pop(context, p),
                                  );
                                },
                              ),
              ),
            ],
          ),
        );
      },
    );
  }
}
