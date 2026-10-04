class UserProfile {
  final String email;
  final String name;
  final String role;
  final String userType; // 'company_staff' | 'seller' | 'app_client'
  final String token;
  final String? companyDb;
  final String? businessName;

  UserProfile({
    required this.email,
    required this.name,
    required this.role,
    required this.userType,
    required this.token,
    this.companyDb,
    this.businessName,
  });

  bool get isCorporateSeller => userType == 'seller' || userType == 'company_staff';

  factory UserProfile.fromLoginResponse(Map<String, dynamic> json) {
    final user = Map<String, dynamic>.from(json['user'] ?? {});
    return UserProfile(
      email: user['email']?.toString() ?? '',
      name: user['name']?.toString() ?? 'Usuario',
      role: user['role']?.toString() ?? 'seller',
      userType: user['user_type']?.toString() ?? 'company_staff',
      companyDb: user['company_db']?.toString(),
      businessName: user['business_name']?.toString(),
      token: json['token']?.toString() ?? '',
    );
  }
}
