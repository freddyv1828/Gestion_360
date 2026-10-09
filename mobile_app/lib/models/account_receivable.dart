class AccountReceivable {
  final String? clientId;
  final String clientName;
  final String clientRif;
  final double invoicedTotal;
  final double collectedTotal;
  final double balanceDue;

  AccountReceivable({
    this.clientId,
    required this.clientName,
    required this.clientRif,
    required this.invoicedTotal,
    required this.collectedTotal,
    required this.balanceDue,
  });

  factory AccountReceivable.fromJson(Map<String, dynamic> json) {
    return AccountReceivable(
      clientId: json['client_id']?.toString(),
      clientName: json['client_name']?.toString() ?? '',
      clientRif: json['client_rif']?.toString() ?? '',
      invoicedTotal: (json['invoiced_total'] as num?)?.toDouble() ?? 0.0,
      collectedTotal: (json['collected_total'] as num?)?.toDouble() ?? 0.0,
      balanceDue: (json['balance_due'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class AgingBucketSummary {
  final String label;
  final int count;
  final double total;

  AgingBucketSummary({required this.label, required this.count, required this.total});

  factory AgingBucketSummary.fromJson(Map<String, dynamic> json) {
    return AgingBucketSummary(
      label: json['label']?.toString() ?? '',
      count: (json['count'] as num?)?.toInt() ?? 0,
      total: (json['total'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class DashboardSummary {
  final int clientsCount;
  final int openOrdersCount;
  final double accountsReceivableTotal;
  final List<AccountReceivable> accountsReceivableTop;
  final List<AgingBucketSummary> agingBuckets;
  final List<Map<String, dynamic>> recentOrders;

  DashboardSummary({
    required this.clientsCount,
    required this.openOrdersCount,
    required this.accountsReceivableTotal,
    required this.accountsReceivableTop,
    required this.agingBuckets,
    required this.recentOrders,
  });

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    final rawTop = List<Map<String, dynamic>>.from(json['accounts_receivable_top'] ?? []);
    final agingSummary = Map<String, dynamic>.from(json['aging_summary'] ?? {});
    final rawBuckets = List<Map<String, dynamic>>.from(agingSummary['buckets'] ?? []);
    return DashboardSummary(
      clientsCount: (json['clients_count'] as num?)?.toInt() ?? 0,
      openOrdersCount: (json['open_orders_count'] as num?)?.toInt() ?? 0,
      accountsReceivableTotal: (json['accounts_receivable_total'] as num?)?.toDouble() ?? 0.0,
      accountsReceivableTop: rawTop.map((r) => AccountReceivable.fromJson(r)).toList(),
      agingBuckets: rawBuckets.map((b) => AgingBucketSummary.fromJson(b)).toList(),
      recentOrders: List<Map<String, dynamic>>.from(json['recent_orders'] ?? []),
    );
  }
}
