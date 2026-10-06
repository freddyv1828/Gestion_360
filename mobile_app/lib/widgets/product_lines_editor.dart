import 'package:flutter/material.dart';
import '../models/seller_product.dart';

const _kGreen = Color(0xFF10B981);

class ProductLineDraft {
  SellerProduct? product;
  double quantity;
  ProductLineDraft({this.product, this.quantity = 1});
}

/// Editor reutilizable de líneas de artículos para Pedidos y Presupuestos.
/// Si [warehouseId] no es null, muestra la disponibilidad reservable de ese
/// almacén junto a cada artículo seleccionado.
class ProductLinesEditor extends StatefulWidget {
  final List<SellerProduct> products;
  final String? warehouseId;
  final ValueChanged<List<Map<String, dynamic>>> onChanged;

  const ProductLinesEditor({
    super.key,
    required this.products,
    required this.onChanged,
    this.warehouseId,
  });

  @override
  State<ProductLinesEditor> createState() => _ProductLinesEditorState();
}

class _ProductLinesEditorState extends State<ProductLinesEditor> {
  final List<ProductLineDraft> _lines = [ProductLineDraft()];

  void _emit() {
    final items = _lines
        .where((l) => l.product != null && l.quantity > 0)
        .map((l) => {'product_id': l.product!.id, 'quantity': l.quantity})
        .toList();
    widget.onChanged(items);
  }

  Widget _buildLine(int idx, ProductLineDraft line) {
    final availability = line.product?.availabilityFor(widget.warehouseId);
    final showAvailability = line.product != null && widget.warehouseId != null;

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                flex: 3,
                child: DropdownButtonFormField<SellerProduct>(
                  initialValue: line.product,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Artículo', isDense: true),
                  items: widget.products
                      .map((p) => DropdownMenuItem(
                            value: p,
                            child: Text('${p.name} (${p.sku})', overflow: TextOverflow.ellipsis),
                          ))
                      .toList(),
                  onChanged: (p) {
                    setState(() => line.product = p);
                    _emit();
                  },
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                flex: 1,
                child: TextFormField(
                  initialValue: '1',
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Cant.', isDense: true),
                  onChanged: (v) {
                    line.quantity = double.tryParse(v) ?? 0;
                    _emit();
                  },
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                onPressed: _lines.length == 1
                    ? null
                    : () {
                        setState(() => _lines.removeAt(idx));
                        _emit();
                      },
              ),
            ],
          ),
          if (showAvailability)
            Padding(
              padding: const EdgeInsets.only(top: 4, left: 4),
              child: Text(
                'Disponible en almacén: ${availability ?? 0}',
                style: TextStyle(
                  fontSize: 11,
                  color: (availability ?? 0) > 0 ? Colors.grey.shade600 : Colors.redAccent,
                ),
              ),
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
        TextButton.icon(
          onPressed: () => setState(() => _lines.add(ProductLineDraft())),
          icon: const Icon(Icons.add, color: _kGreen, size: 18),
          label: const Text('Agregar línea', style: TextStyle(color: _kGreen)),
        ),
      ],
    );
  }
}
