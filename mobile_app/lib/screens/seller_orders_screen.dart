import 'package:flutter/material.dart';
import '../models/seller_order.dart';
import '../models/seller_product.dart';
import '../services/api_service.dart';
import '../widgets/product_lines_editor.dart';
import '../widgets/status_badge.dart';
import 'seller_order_detail_screen.dart';

const _kDark = Color(0xFF0F172A);
const _kGreen = Color(0xFF10B981);
const _kBg = Color(0xFFF8FAFC);

const _kStatusTabs = ['all', 'pendiente', 'en_picking', 'listo_facturar', 'facturado', 'anulado'];
const _kStatusTabLabels = {
  'all': 'Todos',
  'pendiente': 'Pendientes',
  'en_picking': 'En Picking',
  'listo_facturar': 'Listos',
  'facturado': 'Facturados',
  'anulado': 'Anulados',
};

class SellerOrdersScreen extends StatefulWidget {
  const SellerOrdersScreen({super.key});

  @override
  State<SellerOrdersScreen> createState() => _SellerOrdersScreenState();
}

class _SellerOrdersScreenState extends State<SellerOrdersScreen> {
  List<SellerOrder> _orders = [];
  bool _isLoading = true;
  String _error = '';
  String _status = 'all';

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
      final data = await ApiService.fetchSellerOrders(status: _status);
      final rawOrders = List<Map<String, dynamic>>.from(data['orders'] ?? []);
      setState(() => _orders = rawOrders.map((o) => SellerOrder.fromJson(o)).toList());
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _openCreateSheet() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => const _NewOrderSheet(),
    );
    if (created == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBg,
      floatingActionButton: FloatingActionButton(
        backgroundColor: _kGreen,
        onPressed: _openCreateSheet,
        child: const Icon(Icons.add, color: Colors.white),
      ),
      body: Column(
        children: [
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              children: _kStatusTabs.map((s) {
                final selected = s == _status;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: ChoiceChip(
                    label: Text(_kStatusTabLabels[s] ?? s),
                    selected: selected,
                    selectedColor: _kGreen,
                    labelStyle: TextStyle(color: selected ? Colors.white : _kDark, fontSize: 12),
                    onSelected: (_) {
                      setState(() => _status = s);
                      _load();
                    },
                  ),
                );
              }).toList(),
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _error.isNotEmpty
                    ? Center(child: Text(_error, style: const TextStyle(color: Colors.red)))
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: _orders.isEmpty
                            ? ListView(
                                children: const [
                                  SizedBox(height: 120),
                                  Center(child: Text('No hay pedidos en este estado.', style: TextStyle(color: Colors.grey))),
                                ],
                              )
                            : ListView.builder(
                                padding: const EdgeInsets.all(16),
                                itemCount: _orders.length,
                                itemBuilder: (ctx, i) {
                                  final o = _orders[i];
                                  return Card(
                                    margin: const EdgeInsets.only(bottom: 10),
                                    elevation: 0,
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(14),
                                      side: BorderSide(color: Colors.grey.shade200),
                                    ),
                                    child: ListTile(
                                      onTap: () => Navigator.push(
                                        context,
                                        MaterialPageRoute(builder: (_) => SellerOrderDetailScreen(orderId: o.id)),
                                      ).then((_) => _load()),
                                      title: Text(o.orderNumber, style: const TextStyle(fontWeight: FontWeight.bold)),
                                      subtitle: Text('${o.clientName} · ${o.items.length} línea(s)'),
                                      trailing: StatusBadge(status: o.status),
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

class _NewOrderSheet extends StatefulWidget {
  const _NewOrderSheet();

  @override
  State<_NewOrderSheet> createState() => _NewOrderSheetState();
}

class _NewOrderSheetState extends State<_NewOrderSheet> {
  bool _loadingData = true;
  String _error = '';
  bool _saving = false;

  List<SellerProduct> _products = [];
  List<SellerWarehouse> _warehouses = [];

  final _manualName = TextEditingController();
  final _manualRif = TextEditingController();
  final _comment = TextEditingController();
  String? _warehouseId;
  String _docType = 'factura_fiscal';
  List<Map<String, dynamic>> _items = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final warehouses = await ApiService.fetchWarehouses();
      final productsData = await ApiService.fetchSellerProducts(perPage: 200);
      setState(() {
        _warehouses = warehouses.map((w) => SellerWarehouse.fromJson(w)).toList();
        _products = List<Map<String, dynamic>>.from(productsData['products'] ?? [])
            .map((p) => SellerProduct.fromJson(p))
            .toList();
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loadingData = false);
    }
  }

  Future<void> _submit() async {
    final clientName = _manualName.text.trim();
    if (clientName.isEmpty) {
      setState(() => _error = 'Ingrese el nombre del cliente.');
      return;
    }
    if (_warehouseId == null) {
      setState(() => _error = 'Seleccione el almacén de despacho.');
      return;
    }
    if (_items.isEmpty) {
      setState(() => _error = 'Agregue al menos un artículo.');
      return;
    }
    setState(() {
      _saving = true;
      _error = '';
    });
    try {
      await ApiService.createSellerOrder(
        clientName: clientName,
        clientRif: _manualRif.text.trim(),
        warehouseId: _warehouseId!,
        docType: _docType,
        comment: _comment.text.trim(),
        items: _items,
      );
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loadingData) {
      return const SizedBox(height: 200, child: Center(child: CircularProgressIndicator()));
    }
    return Padding(
      padding: EdgeInsets.only(
        left: 20, right: 20, top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Nuevo Pedido', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: _kDark)),
            const SizedBox(height: 16),
            TextField(controller: _manualName, decoration: const InputDecoration(labelText: 'Cliente / Razón Social *')),
            const SizedBox(height: 10),
            TextField(controller: _manualRif, decoration: const InputDecoration(labelText: 'RIF / Cédula')),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _warehouseId,
              decoration: const InputDecoration(labelText: 'Almacén de Despacho *'),
              items: _warehouses.map((w) => DropdownMenuItem(value: w.id, child: Text(w.name))).toList(),
              onChanged: (v) => setState(() => _warehouseId = v),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: RadioListTile<String>(
                    value: 'factura_fiscal',
                    groupValue: _docType,
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Factura Fiscal', style: TextStyle(fontSize: 12)),
                    onChanged: (v) => setState(() => _docType = v ?? 'factura_fiscal'),
                  ),
                ),
                Expanded(
                  child: RadioListTile<String>(
                    value: 'nota_entrega',
                    groupValue: _docType,
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Nota de Entrega', style: TextStyle(fontSize: 12)),
                    onChanged: (v) => setState(() => _docType = v ?? 'factura_fiscal'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            const Text('Artículos', style: TextStyle(fontWeight: FontWeight.bold, color: _kDark)),
            const SizedBox(height: 8),
            ProductLinesEditor(
              products: _products,
              warehouseId: _warehouseId,
              onChanged: (items) => _items = items,
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _comment,
              decoration: const InputDecoration(labelText: 'Comentario del pedido'),
            ),
            if (_error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(_error, style: const TextStyle(color: Colors.red, fontSize: 12)),
              ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                onPressed: _saving ? null : _submit,
                style: ElevatedButton.styleFrom(backgroundColor: _kGreen, foregroundColor: Colors.white),
                child: _saving
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Crear Pedido y Bloquear Mercancía'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
