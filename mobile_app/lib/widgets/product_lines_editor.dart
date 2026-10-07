import 'package:flutter/material.dart';
import '../models/seller_product.dart';
import 'product_picker_sheet.dart';
import '../theme/app_theme.dart';

const _kGreen = AppColors.green;
const _kDark = AppColors.dark;

class ProductLineDraft {
  SellerProduct product;
  double quantity;
  ProductLineDraft({required this.product, this.quantity = 1});
}

/// Editor reutilizable de líneas de artículos para Pedidos y Presupuestos.
/// Busca y agrega productos mediante [ProductPickerSheet] (con imagen y
/// paginación real) en vez de precargar todo el catálogo en un dropdown.
class ProductLinesEditor extends StatefulWidget {
  final String? warehouseId;
  final ValueChanged<List<Map<String, dynamic>>> onChanged;

  const ProductLinesEditor({
    super.key,
    required this.onChanged,
    this.warehouseId,
  });

  @override
  State<ProductLinesEditor> createState() => _ProductLinesEditorState();
}

class _ProductLinesEditorState extends State<ProductLinesEditor> {
  final List<ProductLineDraft> _lines = [];

  void _emit() {
    final items = _lines
        .where((l) => l.quantity > 0)
        .map((l) => {'product_id': l.product.id, 'quantity': l.quantity})
        .toList();
    widget.onChanged(items);
  }

  Future<void> _addProduct() async {
    final picked = await ProductPickerSheet.show(context, warehouseId: widget.warehouseId);
    if (picked == null) return;
    final existing = _lines.indexWhere((l) => l.product.id == picked.id);
    setState(() {
      if (existing >= 0) {
        _lines[existing].quantity += 1;
      } else {
        _lines.add(ProductLineDraft(product: picked));
      }
    });
    _emit();
  }

  Widget _buildLine(int idx, ProductLineDraft line) {
    final availability = widget.warehouseId != null ? line.product.availabilityFor(widget.warehouseId) : null;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey.shade200),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: Container(
              width: 36,
              height: 36,
              color: const Color(0xFFF1F5F9),
              child: line.product.imageUrl == null
                  ? const Icon(Icons.inventory_2_outlined, color: Colors.grey, size: 16)
                  : Image.network(
                      line.product.imageUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (ctx, err, stack) => const Icon(Icons.inventory_2_outlined, color: Colors.grey, size: 16),
                    ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(line.product.name, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _kDark), maxLines: 1, overflow: TextOverflow.ellipsis),
                Text(
                  '\$${line.product.price.toStringAsFixed(2)}${availability != null ? ' · Disp: ${availability.toStringAsFixed(2)}' : ''}',
                  style: TextStyle(fontSize: 10, color: (availability ?? 1) > 0 ? Colors.grey.shade600 : Colors.redAccent),
                ),
              ],
            ),
          ),
          SizedBox(
            width: 56,
            child: TextFormField(
              initialValue: '${line.quantity}',
              keyboardType: TextInputType.number,
              textAlign: TextAlign.center,
              decoration: const InputDecoration(isDense: true, contentPadding: EdgeInsets.symmetric(vertical: 6)),
              onChanged: (v) {
                line.quantity = double.tryParse(v) ?? 0;
                _emit();
              },
            ),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
            onPressed: () {
              setState(() => _lines.removeAt(idx));
              _emit();
            },
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < _lines.length; i++) _buildLine(i, _lines[i]),
        if (_lines.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text('Ningún artículo agregado todavía.', style: TextStyle(fontSize: 12, color: Colors.grey.shade500)),
          ),
        TextButton.icon(
          onPressed: _addProduct,
          icon: const Icon(Icons.add, color: _kGreen, size: 18),
          label: const Text('Agregar Artículo', style: TextStyle(color: _kGreen)),
        ),
      ],
    );
  }
}
