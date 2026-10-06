import 'package:flutter/material.dart';

/// Mismos colores de estado que el panel web (templates/commercial/orders.html).
const Map<String, Color> kOrderStatusColors = {
  'pendiente': Color(0xFF64748B), // slate
  'en_picking': Color(0xFFD97706), // amber
  'listo_facturar': Color(0xFF4F46E5), // indigo
  'facturado': Color(0xFF059669), // emerald
  'anulado': Color(0xFFE11D48), // rose
};

const Map<String, String> kOrderStatusLabels = {
  'pendiente': 'Pendiente',
  'en_picking': 'En Picking',
  'listo_facturar': 'Listo p/ Facturar',
  'facturado': 'Facturado',
  'anulado': 'Anulado',
};

class StatusBadge extends StatelessWidget {
  final String status;
  const StatusBadge({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final color = kOrderStatusColors[status] ?? Colors.grey;
    final label = kOrderStatusLabels[status] ?? status;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w800),
      ),
    );
  }
}
