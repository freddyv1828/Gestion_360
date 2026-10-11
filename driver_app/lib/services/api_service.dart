import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final String message;
  ApiException(this.message);

  @override
  String toString() => message;
}

class ApiService {
  /// Mismo backend que la app de vendedores (Gestion_360). 10.0.2.2 apunta al
  /// localhost del host desde el emulador de Android; para dispositivo físico
  /// o producción, sobreescribir con --dart-define=API_BASE_URL=https://...
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8080',
  );

  static String? authToken;

  static Map<String, String> get _authHeaders => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${authToken ?? ''}',
      };

  static Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    final response = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  static Future<Map<String, dynamic>> _authGet(String path) async {
    final response = await http.get(Uri.parse('$baseUrl$path'), headers: _authHeaders);
    return _decode(response);
  }

  static Future<Map<String, dynamic>> _authPost(String path, [Map<String, dynamic>? body]) async {
    final response = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: _authHeaders,
      body: body != null ? jsonEncode(body) : null,
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

  static Future<Map<String, dynamic>> login(String email, String password) async {
    final data = await _post('/api/v1/auth/login', {'email': email, 'password': password});
    authToken = data['token'] as String?;
    return data;
  }

  static void logout() {
    authToken = null;
  }

  // ==========================================================================
  // APP DEL CHOFER — /api/v1/driver/* (requieren Authorization: Bearer)
  // ==========================================================================

  static Future<List<Map<String, dynamic>>> fetchMyRoutes() async {
    final data = await _authGet('/api/v1/driver/routes');
    return List<Map<String, dynamic>>.from(data['routes'] ?? []);
  }

  static Future<Map<String, dynamic>> fetchRouteDetail(String routeId) async {
    final data = await _authGet('/api/v1/driver/routes/$routeId');
    return Map<String, dynamic>.from(data['route'] ?? {});
  }

  static Future<String> startRoute(String routeId) async {
    final data = await _authPost('/api/v1/driver/routes/$routeId/start');
    return data['message']?.toString() ?? 'Ruta activada.';
  }

  static Future<String> completeRoute(String routeId) async {
    final data = await _authPost('/api/v1/driver/routes/$routeId/complete');
    return data['message']?.toString() ?? 'Ruta completada.';
  }

  /// Confirma la entrega de una factura con foto + firma (ambas obligatorias
  /// en el backend). La firma llega como PNG generado por el widget de firma,
  /// no como archivo elegido por el usuario.
  static Future<String> confirmDelivery({
    required String invoiceId,
    required File photo,
    required List<int> signaturePngBytes,
    String notes = '',
  }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/v1/driver/invoices/$invoiceId/deliver'),
    );
    request.headers['Authorization'] = 'Bearer ${authToken ?? ''}';
    request.fields['notes'] = notes;
    request.files.add(await http.MultipartFile.fromPath('photo', photo.path));
    request.files.add(http.MultipartFile.fromBytes('signature', signaturePngBytes, filename: 'firma.png'));
    final streamed = await request.send();
    final response = await http.Response.fromStream(streamed);
    final data = _decode(response);
    return data['message']?.toString() ?? 'Entrega confirmada.';
  }
}
