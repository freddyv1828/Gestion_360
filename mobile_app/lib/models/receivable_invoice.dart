class ReceivableInvoice {
  final String invoiceId;
  final String invoiceNumber;
  final String? clientId;
  final String clientName;
  final String clientRif;
  final String? seller;
  final DateTime? createdAt;
  final int daysOutstanding;
  final String agingBucket;
  final String currency;
  final double total;
  final double amountPaid;
  final double balanceDue;

  ReceivableInvoice({
    required this.invoiceId,
    required this.invoiceNumber,
    this.clientId,
    required this.clientName,
    required this.clientRif,
    this.seller,
    this.createdAt,
    required this.daysOutstanding,
    required this.agingBucket,
    required this.currency,
    required this.total,
    required this.amountPaid,
    required this.balanceDue,
  });

  factory ReceivableInvoice.fromJson(Map<String, dynamic> json) {
    return ReceivableInvoice(
      invoiceId: json['invoice_id']?.toString() ?? '',
      invoiceNumber: json['invoice_number']?.toString() ?? '',
      clientId: json['client_id']?.toString(),
      clientName: json['client_name']?.toString() ?? '',
      clientRif: json['client_rif']?.toString() ?? '',
      seller: json['seller']?.toString(),
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      daysOutstanding: (json['days_outstanding'] as num?)?.toInt() ?? 0,
      agingBucket: json['aging_bucket']?.toString() ?? '0-7',
      currency: json['currency']?.toString() ?? 'USD',
      total: (json['total'] as num?)?.toDouble() ?? 0.0,
      amountPaid: (json['amount_paid'] as num?)?.toDouble() ?? 0.0,
      balanceDue: (json['balance_due'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class AgingBucket {
  final String label;
  final int count;
  final double total;

  AgingBucket({required this.label, required this.count, required this.total});

  factory AgingBucket.fromJson(Map<String, dynamic> json) {
    return AgingBucket(
      label: json['label']?.toString() ?? '',
      count: (json['count'] as num?)?.toInt() ?? 0,
      total: (json['total'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class AgingSummary {
  final List<AgingBucket> buckets;
  final double totalBalance;
  final int totalInvoices;

  AgingSummary({required this.buckets, required this.totalBalance, required this.totalInvoices});

  factory AgingSummary.fromJson(Map<String, dynamic> json) {
    final rawBuckets = List<Map<String, dynamic>>.from(json['buckets'] ?? []);
    return AgingSummary(
      buckets: rawBuckets.map((b) => AgingBucket.fromJson(b)).toList(),
      totalBalance: (json['total_balance'] as num?)?.toDouble() ?? 0.0,
      totalInvoices: (json['total_invoices'] as num?)?.toInt() ?? 0,
    );
  }
}

class ReceivablePayment {
  final String id;
  final String invoiceId;
  final String? invoiceNumber;
  final double amount;
  final String currency;
  final String paymentMethod;
  final String? reference;
  final String? notes;
  final String? user;
  final DateTime? createdAt;
  final double? balanceAfter;

  ReceivablePayment({
    required this.id,
    required this.invoiceId,
    this.invoiceNumber,
    required this.amount,
    required this.currency,
    required this.paymentMethod,
    this.reference,
    this.notes,
    this.user,
    this.createdAt,
    this.balanceAfter,
  });

  factory ReceivablePayment.fromJson(Map<String, dynamic> json) {
    return ReceivablePayment(
      id: json['_id']?.toString() ?? '',
      invoiceId: json['invoice_id']?.toString() ?? '',
      invoiceNumber: json['invoice_number']?.toString(),
      amount: (json['amount'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency']?.toString() ?? 'USD',
      paymentMethod: json['payment_method']?.toString() ?? '',
      reference: json['reference']?.toString(),
      notes: json['notes']?.toString(),
      user: json['user']?.toString(),
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      balanceAfter: (json['balance_after'] as num?)?.toDouble(),
    );
  }
}
