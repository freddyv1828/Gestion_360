class UserProfile {
  final String uid;
  final String email;
  final String role; // 'admin' o 'seller'
  final String fullName;
  final bool isActive;

  UserProfile({
    required this.uid,
    required this.email,
    required this.role,
    required this.fullName,
    required this.isActive,
  });

  factory UserProfile.fromMap(String uid, Map<String, dynamic> map) {
    return UserProfile(
      uid: uid,
      email: map['email'] ?? '',
      role: map['role'] ?? 'seller',
      fullName: map['fullName'] ?? '',
      isActive: map['isActive'] ?? true,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'email': email,
      'role': role,
      'fullName': fullName,
      'isActive': isActive,
    };
  }
}