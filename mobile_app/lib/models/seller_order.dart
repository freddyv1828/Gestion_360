class SellerOrderItem {
  final String productId;
  final String name;
  final String sku;
  final String unitType;
  final bool requiresWeighing;
  final double quantity;
  final double unitPrice;
  final bool verified;
  final double? verifiedQuantity;

  SellerOrderItem({
    required this.productId,
    required this.name,
    required this.sku,
    required this.unitType,
    required this.requiresWeighing,
    required this.quantity,
    required this.unitPrice,
    required this.verified,
    this.verifiedQuantity,
  });

  factory SellerOrderItem.fromJson(Map<String, dynamic> json) {
    return SellerOrderItem(
      productId: json['product_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      sku: json['sku']?.toString() ?? '',
      unitType: json['unit_type']?.toString() ?? 'unidad',
      requiresWeighing: json['requires_weighing'] == true,
      quantity: (json['quantity'] as num?)?.toDouble() ?? 0.0,
      unitPrice: (json['unit_price'] as num?)?.toDouble() ?? 0.0,
      verified: json['verified'] == true,
      verifiedQuantity: (json['verified_quantity'] as num?)?.toDouble(),
    );
  }
}

class SellerOrder {
  final String id;
  final String orderNumber;
  final String clientName;
  final String clientRif;
  final String docType; // 'factura_fiscal' | 'nota_entrega'
  final String comment;
  final String status;
  final String warehouseId;
  final String? invoiceId;
  final List<SellerOrderItem> items;

  SellerOrder({
    required this.id,
    required this.orderNumber,
    required this.clientName,
    required this.clientRif,
    required this.docType,
    required this.comment,
    required this.status,
    required this.warehouseId,
    this.invoiceId,
    required this.items,
  });

  factory SellerOrder.fromJson(Map<String, dynamic> json) {
    final rawItems = List<Map<String, dynamic>>.from(json['items'] ?? []);
    return SellerOrder(
      id: json['_id']?.toString() ?? '',
      orderNumber: json['order_number']?.toString() ?? '',
      clientName: json['client_name']?.toString() ?? '',
      clientRif: json['client_rif']?.toString() ?? '',
      docType: json['doc_type']?.toString() ?? 'factura_fiscal',
      comment: json['comment']?.toString() ?? '',
      status: json['status']?.toString() ?? 'pendiente',
      warehouseId: json['warehouse_id']?.toString() ?? '',
      invoiceId: json['invoice_id']?.toString(),
      items: rawItems.map((i) => SellerOrderItem.fromJson(i)).toList(),
    );
  }
}
