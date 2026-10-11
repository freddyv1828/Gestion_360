import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:signature/signature.dart';
import '../models/delivery_route.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

class DeliveryConfirmationScreen extends StatefulWidget {
  final DeliveryStop stop;
  const DeliveryConfirmationScreen({super.key, required this.stop});

  @override
  State<DeliveryConfirmationScreen> createState() => _DeliveryConfirmationScreenState();
}

class _DeliveryConfirmationScreenState extends State<DeliveryConfirmationScreen> {
  final _signatureController = SignatureController(
    penStrokeWidth: 3,
    penColor: AppColors.dark,
    exportBackgroundColor: Colors.white,
  );
  final _notesController = TextEditingController();

  File? _photo;
  bool _isSubmitting = false;
  String _errorMessage = '';

  Future<void> _pickPhoto() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined, color: AppColors.dark),
              title: const Text('Tomar foto de la entrega'),
              onTap: () => Navigator.pop(ctx, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined, color: AppColors.dark),
              title: const Text('Elegir de la galería'),
              onTap: () => Navigator.pop(ctx, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source == null) return;

    final picker = ImagePicker();
    final picked = await picker.pickImage(source: source, imageQuality: 80);
    if (picked != null) {
      setState(() => _photo = File(picked.path));
    }
  }

  Future<void> _submit() async {
    setState(() => _errorMessage = '');

    if (_photo == null) {
      setState(() => _errorMessage = 'Toma una foto de la entrega antes de continuar.');
      return;
    }
    if (_signatureController.isEmpty) {
      setState(() => _errorMessage = 'Pídele al cliente que firme antes de continuar.');
      return;
    }

    setState(() => _isSubmitting = true);
    try {
      final signatureBytes = await _signatureController.toPngBytes();
      if (signatureBytes == null) {
        throw Exception('No se pudo procesar la firma. Intenta de nuevo.');
      }
      final message = await ApiService.confirmDelivery(
        invoiceId: widget.stop.invoiceId,
        photo: _photo!,
        signaturePngBytes: signatureBytes,
        notes: _notesController.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message), backgroundColor: AppColors.green),
      );
      Navigator.pop(context);
    } catch (e) {
      setState(() => _errorMessage = e.toString());
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  void dispose() {
    _signatureController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final stop = widget.stop;
    return Scaffold(
      appBar: AppBar(title: const Text('Confirmar Entrega')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(stop.clientName, style: Theme.of(context).textTheme.titleMedium),
                    if (stop.clientAddress.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(stop.clientAddress, style: const TextStyle(color: AppColors.muted, fontSize: 13)),
                    ],
                    if (stop.clientPhone.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.phone_outlined, size: 14, color: AppColors.muted),
                          const SizedBox(width: 4),
                          Text(stop.clientPhone, style: const TextStyle(color: AppColors.muted, fontSize: 13)),
                        ],
                      ),
                    ],
                    const Divider(height: 20),
                    Text(
                      '${stop.invoiceNumber} — ${stop.itemCount} artículo(s) — ${stop.total.toStringAsFixed(2)} ${stop.currency}',
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
            Text('1. Foto de la entrega', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            GestureDetector(
              onTap: _pickPhoto,
              child: Container(
                height: 180,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: AppColors.bg,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.border),
                ),
                child: _photo == null
                    ? const Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.camera_alt_outlined, size: 32, color: AppColors.muted),
                            SizedBox(height: 8),
                            Text('Tocar para tomar la foto', style: TextStyle(color: AppColors.muted, fontSize: 12)),
                          ],
                        ),
                      )
                    : ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: Image.file(_photo!, fit: BoxFit.cover, width: double.infinity),
                      ),
              ),
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('2. Firma del cliente', style: Theme.of(context).textTheme.titleSmall),
                TextButton.icon(
                  onPressed: () => setState(() => _signatureController.clear()),
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('Borrar'),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Container(
              height: 200,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.border),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Signature(controller: _signatureController, backgroundColor: Colors.white),
              ),
            ),
            const SizedBox(height: 20),
            Text('3. Notas (opcional)', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            TextField(
              controller: _notesController,
              maxLines: 2,
              decoration: const InputDecoration(hintText: 'Ej. Recibido por el encargado del local'),
            ),
            const SizedBox(height: 18),
            if (_errorMessage.isNotEmpty)
              Container(
                width: double.infinity,
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.rose.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.rose.withValues(alpha: 0.25)),
                ),
                child: Text(
                  _errorMessage,
                  style: const TextStyle(color: AppColors.rose, fontSize: 12),
                  textAlign: TextAlign.center,
                ),
              ),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton.icon(
                onPressed: _isSubmitting ? null : _submit,
                icon: _isSubmitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.2),
                      )
                    : const Icon(Icons.check_circle_outline),
                label: Text(_isSubmitting ? 'Enviando...' : 'Confirmar Entrega'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
