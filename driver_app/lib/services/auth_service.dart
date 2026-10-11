import '../models/user_profile.dart';
import 'api_service.dart';

class AuthService {
  UserProfile? _currentUser;

  UserProfile? get currentUser => _currentUser;

  /// Inicia sesión contra el mismo backend/login que el resto de la empresa
  /// (/api/v1/auth/login) — el chofer entra con su propio usuario, sin
  /// necesidad de un endpoint de login separado.
  Future<UserProfile> signInWithEmail(String email, String password) async {
    final response = await ApiService.login(email, password);
    final profile = UserProfile.fromLoginResponse(response);
    _currentUser = profile;
    return profile;
  }

  void signOut() {
    ApiService.logout();
    _currentUser = null;
  }
}
