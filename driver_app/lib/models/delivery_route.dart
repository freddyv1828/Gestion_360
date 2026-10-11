class DeliveryRoute {
  final String id;
  final String routeCode;
  final String destination;
  final String status; // planificada | en_curso | completada | cancelada
  final int stopCount;
  final int deliveredCount;

  DeliveryRoute({
    required this.id,
    required this.routeCode,
    required this.destination,
    required this.status,
    required this.stopCount,
    required this.deliveredCount,
  });

  bool get allDelivered => stopCount > 0 && deliveredCount >= stopCount;

  factory DeliveryRoute.fromJson(Map<String, dynamic> json) {
    return DeliveryRoute(
      id: json['_id']?.toString() ?? '',
      routeCode: json['route_code']?.toString() ?? '',
      destination: json['destination']?.toString() ?? '',
      status: json['status']?.toString() ?? 'planificada',
      stopCount: (json['stop_count'] as num?)?.toInt() ?? 0,
      deliveredCount: (json['delivered_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class DeliveryStop {
  final String invoiceId;
  final String invoiceNumber;
  final String clientName;
  final String clientAddress;
  final String clientPhone;
  final double total;
  final String currency;
  final bool delivered;
  final int itemCount;

  DeliveryStop({
    required this.invoiceId,
    required this.invoiceNumber,
    required this.clientName,
    required this.clientAddress,
    required this.clientPhone,
    required this.total,
    required this.currency,
    required this.delivered,
    required this.itemCount,
  });

  factory DeliveryStop.fromJson(Map<String, dynamic> json) {
    return DeliveryStop(
      invoiceId: json['invoice_id']?.toString() ?? '',
      invoiceNumber: json['invoice_number']?.toString() ?? '',
      clientName: json['client_name']?.toString() ?? '',
      clientAddress: json['client_address']?.toString() ?? '',
      clientPhone: json['client_phone']?.toString() ?? '',
      total: (json['total'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency']?.toString() ?? 'USD',
      delivered: json['delivered_at'] != null,
      itemCount: (json['item_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class DeliveryRouteDetail {
  final String id;
  final String routeCode;
  final String destination;
  final String status;
  final List<DeliveryStop> stops;

  DeliveryRouteDetail({
    required this.id,
    required this.routeCode,
    required this.destination,
    required this.status,
    required this.stops,
  });

  factory DeliveryRouteDetail.fromJson(Map<String, dynamic> json) {
    final rawStops = (json['stops'] as List? ?? []);
    return DeliveryRouteDetail(
      id: json['_id']?.toString() ?? '',
      routeCode: json['route_code']?.toString() ?? '',
      destination: json['destination']?.toString() ?? '',
      status: json['status']?.toString() ?? 'planificada',
      stops: rawStops.map((s) => DeliveryStop.fromJson(Map<String, dynamic>.from(s))).toList(),
    );
  }
}
