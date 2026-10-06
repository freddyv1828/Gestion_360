class SellerProduct {
  final String id;
  final String name;
  final String sku;
  final double price;
  final String unitType;
  final double ivaRate;
  final bool requiresWeighing;
  final Map<String, double> availabilityByWarehouse;

  SellerProduct({
    required this.id,
    required this.name,
    required this.sku,
    required this.price,
    required this.unitType,
    required this.ivaRate,
    required this.requiresWeighing,
    required this.availabilityByWarehouse,
  });

  double availabilityFor(String? warehouseId) {
    if (warehouseId == null) return 0;
    return availabilityByWarehouse[warehouseId] ?? 0;
  }

  factory SellerProduct.fromJson(Map<String, dynamic> json) {
    final rawAvail = Map<String, dynamic>.from(json['availability_by_warehouse'] ?? {});
    return SellerProduct(
      id: json['_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      sku: json['sku']?.toString() ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0.0,
      unitType: json['unit_type']?.toString() ?? 'unidad',
      ivaRate: (json['iva_rate'] as num?)?.toDouble() ?? 16.0,
      requiresWeighing: json['requires_weighing'] == true,
      availabilityByWarehouse: rawAvail.map(
        (k, v) => MapEntry(k, (v as num?)?.toDouble() ?? 0.0),
      ),
    );
  }
}

class SellerWarehouse {
  final String id;
  final String name;
  final String code;

  SellerWarehouse({required this.id, required this.name, required this.code});

  factory SellerWarehouse.fromJson(Map<String, dynamic> json) {
    return SellerWarehouse(
      id: json['_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      code: json['code']?.toString() ?? '',
    );
  }
}
