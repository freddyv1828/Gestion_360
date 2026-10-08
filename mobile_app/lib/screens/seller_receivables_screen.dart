import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/receivable_invoice.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/app_states.dart';

const _kBucketColors = {
  '0-7': AppColors.green,
  '8-15': Color(0xFF0D9488),
  '16-21': AppColors.amber,
  '22-30': Color(0xFFEA580C),
  '31-45': AppColors.rose,
  '46+': Color(0xFFB91C1C),
};

/// Cuentas por Cobrar del vendedor: antigüedad de saldo (aging) + lista de
/// facturas pendientes, con registro de abonos anclado a cada factura —
/// la contraparte móvil del módulo web de Cuentas por Cobrar.
class SellerReceivablesScreen extends StatefulWidget {
  const SellerReceivablesScreen({super.key});

  @override
  State<SellerReceivablesScreen> createState() => _SellerReceivablesScreenState();
}

class _SellerReceivablesScreenState extends State<SellerReceivablesScreen> {
  final _searchController = TextEditingController();
  Timer? _debounce;

  List<ReceivableInvoice> _items = [];
  AgingSummary? _aging;
  String _query = '';
  String _bucket = '';
  bool _isLoading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  // ignore: unused_element
  Future<void> reload() => _load();

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _isLoading = true;
      _error = '';
    });
    try {
      final data = await ApiService.fetchSellerReceivables(search: _query, bucket: _bucket);
      final rawItems = List<Map<String, dynamic>>.from(data['items'] ?? []);
      setState(() {
        _items = rawItems.map((i) => ReceivableInvoice.fromJson(i)).toList();
        _aging = AgingSummary.fromJson(Map<String, dynamic>.from(data['aging'] ?? {}));
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _onQueryChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      _query = value.trim();
      _load();
    });
  }

  void _toggleBucket(String label) {
    setState(() => _bucket = _bucket == label ? '' : label);
    _load();
  }

  Future<void> _openPaymentSheet(ReceivableInvoice inv) async {
    final registered = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => _PaymentSheet(invoice: inv),
    );
    if (registered == true) _load();
  }

  void _openHistorySheet(ReceivableInvoice inv) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => _HistorySheet(invoice: inv),
    );
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
                labelText: 'Buscar por N° Factura, Cliente o RIF',
                prefixIcon: Icon(Icons.search, size: 20),
              ),
              onChanged: _onQueryChanged,
            ),
          ),
          if (_aging != null && _aging!.buckets.isNotEmpty)
            SizedBox(
              height: 86,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _aging!.buckets.length,
                separatorBuilder: (ctx, i) => const SizedBox(width: 8),
                itemBuilder: (ctx, i) {
                  final b = _aging!.buckets[i];
                  final color = _kBucketColors[b.label] ?? AppColors.muted;
                  final selected = _bucket == b.label;
                  return GestureDetector(
                    onTap: () => _toggleBucket(b.label),
                    child: Container(
                      width: 108,
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: selected ? color.withValues(alpha: 0.15) : Colors.white,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: selected ? color : AppColors.border, width: selected ? 1.6 : 1),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text('${b.label} días', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: color)),
                          const SizedBox(height: 4),
                          Text('\$${b.total.toStringAsFixed(2)}', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppColors.dark)),
                          Text('${b.count} factura(s)', style: const TextStyle(fontSize: 9, color: AppColors.muted)),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          const SizedBox(height: 8),
          Expanded(
            child: _isLoading
                ? const AppLoading(message: 'Cargando cuentas por cobrar…')
                : _error.isNotEmpty
                    ? AppErrorState(message: _error, onRetry: _load)
                    : _items.isEmpty
                        ? const AppEmptyState(
                            icon: Icons.scale_outlined,
                            title: 'Sin cuentas por cobrar pendientes',
                            subtitle: 'No hay facturas a crédito con saldo con estos filtros.',
                          )
                        : RefreshIndicator(
                            onRefresh: _load,
                            child: ListView.separated(
                              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                              itemCount: _items.length,
                              separatorBuilder: (ctx, i) => const SizedBox(height: 10),
                              itemBuilder: (ctx, i) {
                                final inv = _items[i];
                                final color = _kBucketColors[inv.agingBucket] ?? AppColors.muted;
                                return Card(
                                  child: Padding(
                                    padding: const EdgeInsets.all(14),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Expanded(
                                              child: Text(inv.invoiceNumber,
                                                  style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, color: AppColors.dark)),
                                            ),
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                              decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(999)),
                                              child: Text('${inv.daysOutstanding} días',
                                                  style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w800)),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 4),
                                        Text(inv.clientName, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.dark)),
                                        Text(inv.clientRif, style: const TextStyle(fontSize: 11, color: AppColors.muted, fontFamily: 'monospace')),
                                        const SizedBox(height: 10),
                                        Row(
                                          children: [
                                            Expanded(
                                              child: Column(
                                                crossAxisAlignment: CrossAxisAlignment.start,
                                                children: [
                                                  const Text('Saldo', style: TextStyle(fontSize: 9, color: AppColors.muted, fontWeight: FontWeight.w700)),
                                                  Text('\$${inv.balanceDue.toStringAsFixed(2)}',
                                                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: AppColors.rose)),
                                                ],
                                              ),
                                            ),
                                            TextButton(onPressed: () => _openHistorySheet(inv), child: const Text('Historial')),
                                            const SizedBox(width: 4),
                                            ElevatedButton(onPressed: () => _openPaymentSheet(inv), child: const Text('Abonar')),
                                          ],
                                        ),
                                      ],
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

class _PaymentSheet extends StatefulWidget {
  final ReceivableInvoice invoice;
  const _PaymentSheet({required this.invoice});

  @override
  State<_PaymentSheet> createState() => _PaymentSheetState();
}

class _PaymentSheetState extends State<_PaymentSheet> {
  late final TextEditingController _amountController;
  final _referenceController = TextEditingController();
  final _notesController = TextEditingController();
  final _discountValueController = TextEditingController();
  String _method = 'Pago Móvil';
  String _currency = 'USD';
  String _discountType = '';
  String _accountId = '';
  bool _saving = false;
  bool _loadingAccounts = true;
  String _error = '';
  List<Map<String, dynamic>> _accounts = [];
  File? _receiptImage;

  static const _methods = ['Pago Móvil', 'Efectivo', 'Transferencia', 'Tarjeta', 'Zelle', 'Binance', 'Otro'];
  static const _currencies = ['USD', 'VES', 'EUR', 'COP'];

  @override
  void initState() {
    super.initState();
    _currency = widget.invoice.currency;
    _amountController = TextEditingController(text: widget.invoice.balanceDue.toStringAsFixed(2));
    _loadAccounts();
  }

  Future<void> _loadAccounts() async {
    try {
      final accounts = await ApiService.fetchSellerBankingAccounts();
      if (mounted) setState(() => _accounts = accounts);
    } catch (_) {
      // Si falla, el vendedor igual puede registrar el abono sin cuenta asociada.
    } finally {
      if (mounted) setState(() => _loadingAccounts = false);
    }
  }

  Future<void> _pickReceiptImage() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.camera, imageQuality: 80);
    if (picked != null) {
      setState(() => _receiptImage = File(picked.path));
    }
  }

  @override
  void dispose() {
    _amountController.dispose();
    _referenceController.dispose();
    _notesController.dispose();
    _discountValueController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final amount = double.tryParse(_amountController.text.replaceAll(',', '.'));
    if (amount == null || amount <= 0) {
      setState(() => _error = 'Ingresa un monto válido.');
      return;
    }
    setState(() {
      _saving = true;
      _error = '';
    });
    try {
      await ApiService.registerReceivablePayment(
        invoiceId: widget.invoice.invoiceId,
        amount: amount,
        currency: _currency,
        paymentMethod: _method,
        accountId: _accountId,
        reference: _referenceController.text.trim(),
        notes: _notesController.text.trim(),
        discountType: _discountType,
        discountValue: _discountValueController.text.trim(),
        receiptImage: _receiptImage,
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
    final inv = widget.invoice;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 8, 20, MediaQuery.of(context).viewInsets.bottom + 24),
      child: SingleChildScrollView(
        child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Registrar Abono', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.dark)),
          const SizedBox(height: 4),
          Text('${inv.invoiceNumber} · ${inv.clientName}', style: const TextStyle(fontSize: 12, color: AppColors.muted)),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: AppColors.bg, borderRadius: BorderRadius.circular(10)),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Saldo pendiente', style: TextStyle(fontSize: 12, color: AppColors.muted)),
                Text('\$${inv.balanceDue.toStringAsFixed(2)} ${inv.currency}',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppColors.rose)),
              ],
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Si el cliente paga de más, el excedente queda como saldo a favor (no se pierde).',
            style: TextStyle(fontSize: 10, color: AppColors.muted, fontStyle: FontStyle.italic),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                flex: 2,
                child: TextField(
                  controller: _amountController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Monto a Abonar *'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: _currency,
                  decoration: const InputDecoration(labelText: 'Moneda'),
                  items: _currencies.map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
                  onChanged: (v) => setState(() => _currency = v ?? 'USD'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _method,
            decoration: const InputDecoration(labelText: 'Método'),
            items: _methods.map((m) => DropdownMenuItem(value: m, child: Text(m))).toList(),
            onChanged: (v) {
              setState(() {
                _method = v ?? 'Pago Móvil';
                if (_method == 'Pago Móvil') _currency = 'VES';
                if (_method == 'Zelle' || _method == 'Binance') _currency = 'USD';
              });
            },
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _accountId.isEmpty ? null : _accountId,
            decoration: InputDecoration(labelText: _loadingAccounts ? 'Cargando cuentas...' : 'Banco/Cuenta al que Pagó'),
            items: _accounts
                .map((a) => DropdownMenuItem<String>(
                      value: a['_id'] as String,
                      child: Text('${a['name']} (${a['currency']})', overflow: TextOverflow.ellipsis),
                    ))
                .toList(),
            onChanged: (v) => setState(() => _accountId = v ?? ''),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _referenceController,
            decoration: const InputDecoration(labelText: 'Referencia / N° de Operación'),
          ),
          const SizedBox(height: 4),
          const Text(
            'Se cruza con el estado de cuenta bancario importado para verificar el pago.',
            style: TextStyle(fontSize: 10, color: AppColors.muted),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: _pickReceiptImage,
            icon: const Icon(Icons.camera_alt_outlined, size: 18),
            label: Text(_receiptImage == null ? 'Adjuntar Captura del Pago' : 'Captura adjunta ✓'),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: _discountType.isEmpty ? '' : _discountType,
                  decoration: const InputDecoration(labelText: 'Descuento Pronto Pago'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('Sin descuento')),
                    DropdownMenuItem(value: 'percentage', child: Text('% Porcentaje')),
                    DropdownMenuItem(value: 'fixed', child: Text('Monto Fijo')),
                  ],
                  onChanged: (v) => setState(() => _discountType = v ?? ''),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _discountValueController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Valor'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          TextField(controller: _notesController, decoration: const InputDecoration(labelText: 'Notas (opcional)')),
          if (_error.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_error, style: const TextStyle(color: AppColors.rose, fontSize: 12)),
            ),
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              onPressed: _saving ? null : _submit,
              child: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.4))
                  : const Text('Registrar Abono'),
            ),
          ),
        ],
        ),
      ),
    );
  }
}

class _HistorySheet extends StatefulWidget {
  final ReceivableInvoice invoice;
  const _HistorySheet({required this.invoice});

  @override
  State<_HistorySheet> createState() => _HistorySheetState();
}

class _HistorySheetState extends State<_HistorySheet> {
  List<ReceivablePayment> _payments = [];
  bool _loading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final raw = await ApiService.fetchReceivablePayments(widget.invoice.invoiceId);
      setState(() => _payments = raw.map((p) => ReceivablePayment.fromJson(p)).toList());
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _download(String format) async {
    final url = ApiService.receivablePaymentsExportUrl(widget.invoice.invoiceId, format: format);
    final uri = Uri.parse(url);
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No se pudo abrir la descarga.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text('Historial — ${widget.invoice.invoiceNumber}',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.dark)),
              ),
              IconButton(
                icon: const Icon(Icons.picture_as_pdf_outlined, color: AppColors.rose, size: 20),
                tooltip: 'Descargar PDF',
                onPressed: () => _download('pdf'),
              ),
              IconButton(
                icon: const Icon(Icons.table_chart_outlined, color: AppColors.greenDark, size: 20),
                tooltip: 'Descargar Excel',
                onPressed: () => _download('excel'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 320,
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error.isNotEmpty
                    ? Center(child: Text(_error, style: const TextStyle(color: AppColors.rose, fontSize: 12)))
                    : _payments.isEmpty
                        ? const Center(child: Text('Esta factura no tiene abonos registrados todavía.', style: TextStyle(color: AppColors.muted, fontSize: 12)))
                        : ListView.separated(
                            itemCount: _payments.length,
                            separatorBuilder: (ctx, i) => const SizedBox(height: 8),
                            itemBuilder: (ctx, i) {
                              final p = _payments[i];
                              return Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(border: Border.all(color: AppColors.border), borderRadius: BorderRadius.circular(12)),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        Text('\$${p.amount.toStringAsFixed(2)} ${p.currency}',
                                            style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.dark, fontSize: 13)),
                                        if (p.createdAt != null)
                                          Text('${p.createdAt!.day}/${p.createdAt!.month}/${p.createdAt!.year}',
                                              style: const TextStyle(fontSize: 11, color: AppColors.muted)),
                                      ],
                                    ),
                                    Text('${p.paymentMethod}${p.reference?.isNotEmpty == true ? ' · Ref: ${p.reference}' : ''}',
                                        style: const TextStyle(fontSize: 11, color: AppColors.muted)),
                                    if (p.referenceVerified == true)
                                      const Padding(
                                        padding: EdgeInsets.only(top: 2),
                                        child: Text('✓ Verificado en banco', style: TextStyle(fontSize: 10, color: AppColors.greenDark, fontWeight: FontWeight.w700)),
                                      )
                                    else if (p.referenceVerified == false)
                                      const Padding(
                                        padding: EdgeInsets.only(top: 2),
                                        child: Text('⚠ Sin verificar en banco', style: TextStyle(fontSize: 10, color: AppColors.amber, fontWeight: FontWeight.w700)),
                                      ),
                                    if (p.user != null) Text(p.user!, style: const TextStyle(fontSize: 10, color: AppColors.mutedLight)),
                                    if (p.discountAmount != null && p.discountAmount! > 0)
                                      Padding(
                                        padding: const EdgeInsets.only(top: 2),
                                        child: Text('Descuento pronto pago: ${p.discountAmount!.toStringAsFixed(2)} ${p.currency}',
                                            style: const TextStyle(fontSize: 10, color: Color(0xFF0D9488), fontWeight: FontWeight.w700)),
                                      ),
                                    if (p.excessToCreditUsd != null && p.excessToCreditUsd! > 0)
                                      Padding(
                                        padding: const EdgeInsets.only(top: 2),
                                        child: Text('Excedente a saldo a favor: \$${p.excessToCreditUsd!.toStringAsFixed(2)}',
                                            style: const TextStyle(fontSize: 10, color: Color(0xFF6366F1), fontWeight: FontWeight.w700)),
                                      ),
                                    if (p.receiptImageKey?.isNotEmpty == true)
                                      Padding(
                                        padding: const EdgeInsets.only(top: 4),
                                        child: InkWell(
                                          onTap: () => launchUrl(
                                            Uri.parse(ApiService.receiptImageUrl(p.receiptImageKey!)),
                                            mode: LaunchMode.externalApplication,
                                          ),
                                          child: const Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              Icon(Icons.attachment, size: 13, color: AppColors.dark),
                                              SizedBox(width: 4),
                                              Text('Ver comprobante', style: TextStyle(fontSize: 11, color: AppColors.dark, fontWeight: FontWeight.w700, decoration: TextDecoration.underline)),
                                            ],
                                          ),
                                        ),
                                      ),
                                    if (p.notes?.isNotEmpty == true)
                                      Padding(
                                        padding: const EdgeInsets.only(top: 4),
                                        child: Text('"${p.notes}"', style: const TextStyle(fontSize: 11, color: AppColors.muted, fontStyle: FontStyle.italic)),
                                      ),
                                  ],
                                ),
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}
