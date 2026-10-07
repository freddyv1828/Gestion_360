import 'dart:async';
import 'package:flutter/material.dart';
import '../models/seller_client.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

const _kGreen = AppColors.green;
const _kDark = AppColors.dark;

/// Campo de cliente con búsqueda contra los clientes YA guardados en la BD
/// (se vincula por client_id si se selecciona uno) con respaldo de cliente
/// ocasional (nombre/RIF libres) si no se selecciona ninguno.
class ClientSearchField extends StatefulWidget {
  final ValueChanged<SellerClient?> onClientSelected;
  final TextEditingController manualNameController;
  final TextEditingController manualRifController;

  const ClientSearchField({
    super.key,
    required this.onClientSelected,
    required this.manualNameController,
    required this.manualRifController,
  });

  @override
  State<ClientSearchField> createState() => _ClientSearchFieldState();
}

class _ClientSearchFieldState extends State<ClientSearchField> {
  final _searchController = TextEditingController();
  Timer? _debounce;
  List<SellerClient> _results = [];
  bool _searching = false;
  SellerClient? _selected;

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _onQueryChanged(String query) {
    _debounce?.cancel();
    if (_selected != null) {
      setState(() => _selected = null);
      widget.onClientSelected(null);
    }
    if (query.trim().length < 2) {
      setState(() => _results = []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 350), () async {
      setState(() => _searching = true);
      try {
        final raw = await ApiService.fetchSellerClients(search: query.trim());
        if (!mounted) return;
        setState(() => _results = raw.map((c) => SellerClient.fromJson(c)).toList());
      } catch (_) {
        if (mounted) setState(() => _results = []);
      } finally {
        if (mounted) setState(() => _searching = false);
      }
    });
  }

  void _select(SellerClient client) {
    setState(() {
      _selected = client;
      _results = [];
      _searchController.text = client.name;
    });
    widget.onClientSelected(client);
  }

  void _clearSelection() {
    setState(() {
      _selected = null;
      _searchController.clear();
      _results = [];
    });
    widget.onClientSelected(null);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _searchController,
          enabled: _selected == null,
          decoration: InputDecoration(
            labelText: 'Buscar cliente existente (nombre, RIF o correo)',
            prefixIcon: const Icon(Icons.search, size: 20),
            suffixIcon: _searching
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                  )
                : _selected != null
                    ? IconButton(icon: const Icon(Icons.close, size: 18), onPressed: _clearSelection)
                    : null,
          ),
          onChanged: _onQueryChanged,
        ),
        if (_results.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 4),
            constraints: const BoxConstraints(maxHeight: 180),
            decoration: BoxDecoration(
              border: Border.all(color: Colors.grey.shade300),
              borderRadius: BorderRadius.circular(10),
            ),
            child: ListView.separated(
              shrinkWrap: true,
              itemCount: _results.length,
              separatorBuilder: (ctx, i) => const Divider(height: 1),
              itemBuilder: (ctx, i) {
                final c = _results[i];
                return ListTile(
                  dense: true,
                  title: Text(c.name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  subtitle: Text(c.rifCedula, style: const TextStyle(fontSize: 11)),
                  onTap: () => _select(c),
                );
              },
            ),
          ),
        if (_selected != null)
          Container(
            margin: const EdgeInsets.only(top: 6),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: _kGreen.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _kGreen.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.check_circle, color: _kGreen, size: 16),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    '${_selected!.name} · ${_selected!.rifCedula}',
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _kDark),
                  ),
                ),
              ],
            ),
          ),
        if (_selected == null) ...[
          const SizedBox(height: 10),
          Text('¿No existe? Ingrésalo como cliente ocasional:', style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
          const SizedBox(height: 6),
          TextField(
            controller: widget.manualNameController,
            decoration: const InputDecoration(labelText: 'Cliente / Razón Social *', isDense: true),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: widget.manualRifController,
            decoration: const InputDecoration(labelText: 'RIF / Cédula', isDense: true),
          ),
        ],
      ],
    );
  }
}
