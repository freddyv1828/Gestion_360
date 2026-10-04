import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final String message;
  ApiException(this.message);

  @override
  String toString() => message;
}

class ApiService {
  /// Ajustar según el entorno: 10.0.2.2 apunta al localhost del host
  /// desde el emulador de Android; para dispositivo físico o producción,
  /// sobreescribir con --dart-define=API_BASE_URL=https://...
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8080',
  );

  static String? authToken;

  static Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    final response = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  static Map<String, dynamic> _decode(http.Response response) {
    Map<String, dynamic> data;
    try {
      data = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) {
      throw ApiException('Respuesta inválida del servidor (HTTP ${response.statusCode}).');
    }

    if (response.statusCode >= 400) {
      throw ApiException(data['error']?.toString() ?? 'Error de comunicación con el servidor.');
    }
    return data;
  }

  /// Login unificado: identifica vendedor corporativo (trae su inventario)
  /// o cliente del marketplace.
  static Future<Map<String, dynamic>> login(String email, String password) async {
    final data = await _post('/api/v1/auth/login', {'email': email, 'password': password});
    authToken = data['token'] as String?;
    return data;
  }

  /// Vitrina pública sin autenticación (Guest Browsing).
  static Future<List<Map<String, dynamic>>> fetchMarketplaceCatalog() async {
    final response = await http.get(Uri.parse('$baseUrl/api/v1/marketplace/catalog'));
    final data = _decode(response);
    return List<Map<String, dynamic>>.from(data['products'] ?? []);
  }

  /// Confirma el carrito de compra, con registro/login en caliente del cliente.
  static Future<Map<String, dynamic>> checkout({
    required String email,
    required String password,
    String? name,
    required List<Map<String, dynamic>> items,
  }) async {
    final data = await _post('/api/v1/marketplace/checkout', {
      'email': email,
      'password': password,
      'name': name ?? '',
      'items': items,
    });
    authToken = data['token'] as String?;
    return data;
  }

  static void logout() {
    authToken = null;
  }
}
