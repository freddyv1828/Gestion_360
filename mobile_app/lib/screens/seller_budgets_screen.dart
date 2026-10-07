import 'package:flutter/material.dart';
import '../models/seller_budget.dart';
import '../models/seller_client.dart';
import '../models/seller_product.dart';
import '../services/api_service.dart';
import '../widgets/client_search_field.dart';
import '../widgets/product_lines_editor.dart';

const _kDark = Color(0xFF0F172A);
const _kGreen = Color(0xFF10B981);
const _kBg = Color(0xFFF8FAFC);

const _kBudgetStatusColors = {
  'borrador': Color(0xFF64748B),
  'convertido': Color(0xFF059669),
  'descartado': Color(0xFFE11D48),
};
const _kBudgetStatusLabels = {
  'borrador': 'Borrador',
  'convertido': 'Convertido',
  'descartado': 'Descartado',
};

class SellerBudgetsScreen extends StatefulWidget {
  const SellerBudgetsScreen({super.key});

  @override
  State<SellerBudgetsScreen> createState() => _SellerBudgetsScreenState();
}

class _SellerBudgetsScreenState extends State<SellerBudgetsScreen> {
  List<SellerBudget> _budgets = [];
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
      final data = await ApiService.fetchSellerBudgets();
      final raw = List<Map<String, dynamic>>.from(data['budgets'] ?? []);
      setState(() => _budgets = raw.map((b) => SellerBudget.fromJson(b)).toList());
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
      builder: (ctx) => const _NewBudgetSheet(),
    );
    if (created == true) _load();
  }

  Future<void> _openConvertSheet(SellerBudget budget) async {
    final converted = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => _ConvertBudgetSheet(budget: budget),
    );
    if (converted == true) _load();
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
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Text(_error, style: const TextStyle(color: Colors.red)))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _budgets.isEmpty
                      ? ListView(
                          children: const [
                            SizedBox(height: 120),
                            Center(child: Text('No hay presupuestos todavía.', style: TextStyle(color: Colors.grey))),
                          ],
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: _budgets.length,
                          itemBuilder: (ctx, i) {
                            final b = _budgets[i];
                            final color = _kBudgetStatusColors[b.status] ?? Colors.grey;
                            return Card(
                              margin: const EdgeInsets.only(bottom: 10),
                              elevation: 0,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(14),
                                side: BorderSide(color: Colors.grey.shade200),
                              ),
                              child: ListTile(
                                onTap: b.status == 'borrador' ? () => _openConvertSheet(b) : null,
                                title: Text(b.budgetNumber, style: const TextStyle(fontWeight: FontWeight.bold)),
                                subtitle: Text('${b.clientName} · \$${b.estimatedTotal.toStringAsFixed(2)}'),
                                trailing: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: color.withOpacity(0.12),
                                    borderRadius: BorderRadius.circular(999),
                                  ),
                                  child: Text(
                                    _kBudgetStatusLabels[b.status] ?? b.status,
                                    style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w800),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                ),
    );
  }
}

class _NewBudgetSheet extends StatefulWidget {
  const _NewBudgetSheet();

  @override
  State<_NewBudgetSheet> createState() => _NewBudgetSheetState();
}

class _NewBudgetSheetState extends State<_NewBudgetSheet> {
  bool _saving = false;
  String _error = '';

  SellerClient? _selectedClient;
  final _manualName = TextEditingController();
  final _manualRif = TextEditingController();
  final _comment = TextEditingController();
  List<Map<String, dynamic>> _items = [];

  Future<void> _submit() async {
    final clientName = _selectedClient?.name ?? _manualName.text.trim();
    if (clientName.isEmpty) {
      setState(() => _error = 'Seleccione un cliente o ingrese el nombre manualmente.');
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
      await ApiService.createSellerBudget(
        clientId: _selectedClient?.id ?? '',
        clientName: clientName,
        clientRif: _selectedClient?.rifCedula ?? _manualRif.text.trim(),
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
            const Text('Nuevo Presupuesto', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: _kDark)),
            const Text(
              'Simula un precio con el cliente — no bloquea inventario hasta que se convierta en Pedido.',
              style: TextStyle(fontSize: 11, color: Colors.grey),
            ),
            const SizedBox(height: 16),
            ClientSearchField(
              manualNameController: _manualName,
              manualRifController: _manualRif,
              onClientSelected: (c) => setState(() => _selectedClient = c),
            ),
            const SizedBox(height: 14),
            const Text('Artículos', style: TextStyle(fontWeight: FontWeight.bold, color: _kDark)),
            const SizedBox(height: 8),
            ProductLinesEditor(onChanged: (items) => _items = items),
            const SizedBox(height: 10),
            TextField(controller: _comment, decoration: const InputDecoration(labelText: 'Comentario')),
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
                child: _saving ? const CircularProgressIndicator(color: Colors.white) : const Text('Generar Presupuesto'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ConvertBudgetSheet extends StatefulWidget {
  final SellerBudget budget;
  const _ConvertBudgetSheet({required this.budget});

  @override
  State<_ConvertBudgetSheet> createState() => _ConvertBudgetSheetState();
}

class _ConvertBudgetSheetState extends State<_ConvertBudgetSheet> {
  List<SellerWarehouse> _warehouses = [];
  String? _warehouseId;
  String _docType = 'factura_fiscal';
  bool _loading = true;
  bool _saving = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _loadWarehouses();
  }

  Future<void> _loadWarehouses() async {
    try {
      final raw = await ApiService.fetchWarehouses();
      setState(() => _warehouses = raw.map((w) => SellerWarehouse.fromJson(w)).toList());
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _convert() async {
    if (_warehouseId == null) {
      setState(() => _error = 'Seleccione el almacén de despacho.');
      return;
    }
    setState(() {
      _saving = true;
      _error = '';
    });
    try {
      await ApiService.convertBudget(widget.budget.id, warehouseId: _warehouseId!, docType: _docType);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 20, right: 20, top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: _loading
          ? const SizedBox(height: 150, child: Center(child: CircularProgressIndicator()))
          : Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Convertir ${widget.budget.budgetNumber} en Pedido',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: _kDark)),
                const SizedBox(height: 4),
                Text('Total estimado: \$${widget.budget.estimatedTotal.toStringAsFixed(2)}',
                    style: const TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: _warehouseId,
                  decoration: const InputDecoration(labelText: 'Almacén de Despacho *'),
                  items: _warehouses.map((w) => DropdownMenuItem(value: w.id, child: Text(w.name))).toList(),
                  onChanged: (v) => setState(() => _warehouseId = v),
                ),
                const SizedBox(height: 10),
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
                if (_error.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(_error, style: const TextStyle(color: Colors.red, fontSize: 12)),
                  ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton(
                    onPressed: _saving ? null : _convert,
                    style: ElevatedButton.styleFrom(backgroundColor: _kGreen, foregroundColor: Colors.white),
                    child: _saving
                        ? const CircularProgressIndicator(color: Colors.white)
                        : const Text('Convertir en Pedido'),
                  ),
                ),
              ],
            ),
    );
  }
}
