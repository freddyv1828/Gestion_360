class UserProfile {
  final String email;
  final String name;
  final String role;
  final String token;
  final String? companyDb;
  final String? businessName;

  UserProfile({
    required this.email,
    required this.name,
    required this.role,
    required this.token,
    this.companyDb,
    this.businessName,
  });

  factory UserProfile.fromLoginResponse(Map<String, dynamic> json) {
    final user = Map<String, dynamic>.from(json['user'] ?? {});
    return UserProfile(
      email: user['email']?.toString() ?? '',
      name: user['name']?.toString() ?? 'Chofer',
      role: user['role']?.toString() ?? 'chofer',
      companyDb: user['company_db']?.toString(),
      businessName: user['business_name']?.toString(),
      token: json['token']?.toString() ?? '',
    );
  }
}
