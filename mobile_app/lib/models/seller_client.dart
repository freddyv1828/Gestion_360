class SellerClient {
  final String id;
  final String name;
  final String rifCedula;
  final String clientType; // 'fiscal' | 'natural'
  final String email;
  final String phone;
  final String address;
  final double creditLimit;

  SellerClient({
    required this.id,
    required this.name,
    required this.rifCedula,
    required this.clientType,
    required this.email,
    required this.phone,
    required this.address,
    required this.creditLimit,
  });

  factory SellerClient.fromJson(Map<String, dynamic> json) {
    return SellerClient(
      id: json['_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      rifCedula: json['rif_cedula']?.toString() ?? '',
      clientType: json['client_type']?.toString() ?? 'fiscal',
      email: json['email']?.toString() ?? '',
      phone: json['phone']?.toString() ?? '',
      address: json['address']?.toString() ?? '',
      creditLimit: (json['credit_limit'] as num?)?.toDouble() ?? 0.0,
    );
  }
}
