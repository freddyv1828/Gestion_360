class SellerBudgetItem {
  final String productId;
  final String name;
  final String sku;
  final double quantity;
  final double unitPrice;
  final double total;

  SellerBudgetItem({
    required this.productId,
    required this.name,
    required this.sku,
    required this.quantity,
    required this.unitPrice,
    required this.total,
  });

  factory SellerBudgetItem.fromJson(Map<String, dynamic> json) {
    return SellerBudgetItem(
      productId: json['product_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      sku: json['sku']?.toString() ?? '',
      quantity: (json['quantity'] as num?)?.toDouble() ?? 0.0,
      unitPrice: (json['unit_price'] as num?)?.toDouble() ?? 0.0,
      total: (json['total'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class SellerBudget {
  final String id;
  final String budgetNumber;
  final String clientName;
  final String clientRif;
  final String comment;
  final double estimatedTotal;
  final String status; // 'borrador' | 'convertido' | 'descartado'
  final String? orderId;
  final List<SellerBudgetItem> items;

  SellerBudget({
    required this.id,
    required this.budgetNumber,
    required this.clientName,
    required this.clientRif,
    required this.comment,
    required this.estimatedTotal,
    required this.status,
    this.orderId,
    required this.items,
  });

  factory SellerBudget.fromJson(Map<String, dynamic> json) {
    final rawItems = List<Map<String, dynamic>>.from(json['items'] ?? []);
    return SellerBudget(
      id: json['_id']?.toString() ?? '',
      budgetNumber: json['budget_number']?.toString() ?? '',
      clientName: json['client_name']?.toString() ?? '',
      clientRif: json['client_rif']?.toString() ?? '',
      comment: json['comment']?.toString() ?? '',
      estimatedTotal: (json['estimated_total'] as num?)?.toDouble() ?? 0.0,
      status: json['status']?.toString() ?? 'borrador',
      orderId: json['order_id']?.toString(),
      items: rawItems.map((i) => SellerBudgetItem.fromJson(i)).toList(),
    );
  }
}
