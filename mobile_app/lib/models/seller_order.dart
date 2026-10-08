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

class OrderDelivery {
  final String status; // 'sin_ruta' | 'planificada' | 'en_curso' | 'completada' | 'cancelada'
  final String label;
  final String? routeCode;
  final String? vehiclePlate;
  final String? driverName;
  final String? invoiceNumber;

  OrderDelivery({
    required this.status,
    required this.label,
    this.routeCode,
    this.vehiclePlate,
    this.driverName,
    this.invoiceNumber,
  });

  factory OrderDelivery.fromJson(Map<String, dynamic> json) {
    return OrderDelivery(
      status: json['status']?.toString() ?? 'sin_ruta',
      label: json['label']?.toString() ?? '',
      routeCode: json['route_code']?.toString(),
      vehiclePlate: json['vehicle_plate']?.toString(),
      driverName: json['driver_name']?.toString(),
      invoiceNumber: json['invoice_number']?.toString(),
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
  final OrderDelivery? delivery;
  final String? deliveryLabel;
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
    this.delivery,
    this.deliveryLabel,
    required this.items,
  });

  /// Etiqueta de entrega a mostrar: usa el objeto `delivery` completo (detalle
  /// de pedido) si existe, o el `delivery_label` plano (listado) si no.
  String? get effectiveDeliveryLabel => delivery?.label ?? deliveryLabel;

  factory SellerOrder.fromJson(Map<String, dynamic> json) {
    final rawItems = List<Map<String, dynamic>>.from(json['items'] ?? []);
    final rawDelivery = json['delivery'];
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
      delivery: rawDelivery is Map ? OrderDelivery.fromJson(Map<String, dynamic>.from(rawDelivery)) : null,
      deliveryLabel: json['delivery_label']?.toString(),
      items: rawItems.map((i) => SellerOrderItem.fromJson(i)).toList(),
    );
  }
}
