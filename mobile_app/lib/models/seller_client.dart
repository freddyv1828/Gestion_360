class SellerClient {
  final String id;
  final String name;
  final String rifCedula;
  final String email;
  final String phone;
  final String clientType;

  SellerClient({
    required this.id,
    required this.name,
    required this.rifCedula,
    required this.email,
    required this.phone,
    required this.clientType,
  });

  factory SellerClient.fromJson(Map<String, dynamic> json) {
    return SellerClient(
      id: json['_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      rifCedula: json['rif_cedula']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      phone: json['phone']?.toString() ?? '',
      clientType: json['client_type']?.toString() ?? 'fiscal',
    );
  }
}
