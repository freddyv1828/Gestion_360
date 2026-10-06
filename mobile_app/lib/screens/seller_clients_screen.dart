import 'package:flutter/material.dart';
import '../models/seller_client.dart';
import '../services/api_service.dart';

const _kDark = Color(0xFF0F172A);
const _kGreen = Color(0xFF10B981);
const _kBg = Color(0xFFF8FAFC);

class SellerClientsScreen extends StatefulWidget {
  const SellerClientsScreen({super.key});

  @override
  State<SellerClientsScreen> createState() => _SellerClientsScreenState();
}

class _SellerClientsScreenState extends State<SellerClientsScreen> {
  List<SellerClient> _clients = [];
  bool _isLoading = true;
  String _error = '';
  String _search = '';

  @override
  void initState() {
    super.initState();
    _loadClients();
  }

  Future<void> _loadClients() async {
    setState(() {
      _isLoading = true;
      _error = '';
    });
    try {
      final raw = await ApiService.fetchSellerClients();
      setState(() {
        _clients = raw.map((c) => SellerClient.fromJson(c)).toList();
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  List<SellerClient> get _filtered {
    if (_search.isEmpty) return _clients;
    final q = _search.toLowerCase();
    return _clients
        .where((c) => c.name.toLowerCase().contains(q) || c.rifCedula.toLowerCase().contains(q))
        .toList();
  }

  void _openCreateDialog() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => _NewClientSheet(onCreated: _loadClients),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBg,
      floatingActionButton: FloatingActionButton(
        backgroundColor: _kGreen,
        onPressed: _openCreateDialog,
        child: const Icon(Icons.add, color: Colors.white),
      ),
      body: RefreshIndicator(
        onRefresh: _loadClients,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: TextField(
                onChanged: (v) => setState(() => _search = v),
                decoration: InputDecoration(
                  hintText: 'Buscar por nombre o RIF/Cédula...',
                  prefixIcon: const Icon(Icons.search, size: 20),
                  filled: true,
                  fillColor: Colors.white,
                  contentPadding: const EdgeInsets.symmetric(vertical: 0, horizontal: 12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: Colors.grey.shade300),
                  ),
                ),
              ),
            ),
            if (_isLoading) const Expanded(child: Center(child: CircularProgressIndicator()))
            else if (_error.isNotEmpty)
              Expanded(child: Center(child: Text(_error, style: const TextStyle(color: Colors.red))))
            else
              Expanded(
                child: _filtered.isEmpty
                    ? const Center(child: Text('No hay clientes registrados.', style: TextStyle(color: Colors.grey)))
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: _filtered.length,
                        itemBuilder: (ctx, i) {
                          final c = _filtered[i];
                          return Card(
                            margin: const EdgeInsets.only(bottom: 10),
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14),
                              side: BorderSide(color: Colors.grey.shade200),
                            ),
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor: _kDark,
                                child: Text(
                                  c.name.isNotEmpty ? c.name[0].toUpperCase() : '?',
                                  style: const TextStyle(color: Colors.white),
                                ),
                              ),
                              title: Text(c.name, style: const TextStyle(fontWeight: FontWeight.bold)),
                              subtitle: Text('${c.rifCedula} · ${c.clientType == 'fiscal' ? 'Fiscal' : 'Natural'}'),
                              trailing: c.creditLimit > 0
                                  ? Text('\$${c.creditLimit.toStringAsFixed(0)}',
                                      style: const TextStyle(color: _kGreen, fontWeight: FontWeight.bold))
                                  : null,
                            ),
                          );
                        },
                      ),
              ),
          ],
        ),
      ),
    );
  }
}

class _NewClientSheet extends StatefulWidget {
  final VoidCallback onCreated;
  const _NewClientSheet({required this.onCreated});

  @override
  State<_NewClientSheet> createState() => _NewClientSheetState();
}

class _NewClientSheetState extends State<_NewClientSheet> {
  final _name = TextEditingController();
  final _rif = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();
  final _credit = TextEditingController(text: '0');
  String _type = 'fiscal';
  bool _saving = false;
  String _error = '';

  Future<void> _save() async {
    if (_name.text.trim().isEmpty || _rif.text.trim().isEmpty) {
      setState(() => _error = 'Nombre y RIF/Cédula son obligatorios.');
      return;
    }
    setState(() {
      _saving = true;
      _error = '';
    });
    try {
      await ApiService.createSellerClient(
        name: _name.text.trim(),
        rifCedula: _rif.text.trim(),
        clientType: _type,
        email: _email.text.trim(),
        phone: _phone.text.trim(),
        address: _address.text.trim(),
        creditLimit: double.tryParse(_credit.text.trim()) ?? 0,
      );
      widget.onCreated();
      if (mounted) Navigator.pop(context);
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
            const Text('Nuevo Cliente', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: _kDark)),
            const SizedBox(height: 16),
            TextField(controller: _name, decoration: const InputDecoration(labelText: 'Nombre / Razón Social *')),
            const SizedBox(height: 10),
            TextField(controller: _rif, decoration: const InputDecoration(labelText: 'RIF / Cédula *')),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _type,
              decoration: const InputDecoration(labelText: 'Tipo de Cliente'),
              items: const [
                DropdownMenuItem(value: 'fiscal', child: Text('Fiscal (RIF)')),
                DropdownMenuItem(value: 'natural', child: Text('Natural (Cédula)')),
              ],
              onChanged: (v) => setState(() => _type = v ?? 'fiscal'),
            ),
            const SizedBox(height: 10),
            TextField(controller: _email, decoration: const InputDecoration(labelText: 'Correo')),
            const SizedBox(height: 10),
            TextField(controller: _phone, decoration: const InputDecoration(labelText: 'Teléfono')),
            const SizedBox(height: 10),
            TextField(controller: _address, decoration: const InputDecoration(labelText: 'Dirección')),
            const SizedBox(height: 10),
            TextField(
              controller: _credit,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Límite de Crédito (\$)'),
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
                onPressed: _saving ? null : _save,
                style: ElevatedButton.styleFrom(backgroundColor: _kGreen, foregroundColor: Colors.white),
                child: _saving
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Guardar Cliente'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
