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

  /// Headers autenticados para los endpoints /api/v1/seller/*.
  static Map<String, String> get _authHeaders => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${authToken ?? ''}',
      };

  static Future<Map<String, dynamic>> _authGet(String path) async {
    final response = await http.get(Uri.parse('$baseUrl$path'), headers: _authHeaders);
    return _decode(response);
  }

  static Future<Map<String, dynamic>> _authPost(String path, Map<String, dynamic> body) async {
    final response = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: _authHeaders,
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

  // ==========================================================================
  // APP MÓVIL DEL VENDEDOR — /api/v1/seller/* (requieren Authorization: Bearer)
  // ==========================================================================

  static Future<Map<String, dynamic>> fetchSellerDashboard() async {
    return _authGet('/api/v1/seller/dashboard');
  }

  /// Búsqueda de clientes existentes para vincular en Pedidos/Presupuestos.
  /// Sin `search`, trae solo los primeros [limit] (no el directorio completo).
  static Future<List<Map<String, dynamic>>> fetchSellerClients({
    String search = '',
    int limit = 20,
  }) async {
    final data = await fetchSellerClientsPage(search: search, limit: limit);
    return List<Map<String, dynamic>>.from(data['clients'] ?? []);
  }

  /// Igual que [fetchSellerClients] pero retorna el sobre completo con
  /// paginación (`total_pages`), para el directorio completo de clientes.
  static Future<Map<String, dynamic>> fetchSellerClientsPage({
    String search = '',
    int limit = 20,
    int page = 1,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/seller/clients').replace(queryParameters: {
      if (search.isNotEmpty) 'search': search,
      'limit': '$limit',
      'page': '$page',
    });
    final response = await http.get(uri, headers: _authHeaders);
    return _decode(response);
  }

  static Future<Map<String, dynamic>> fetchSellerProducts({
    int page = 1,
    int perPage = 50,
    String search = '',
    String warehouseId = '',
  }) async {
    final query = {
      'page': '$page',
      'per_page': '$perPage',
      if (search.isNotEmpty) 'search': search,
      if (warehouseId.isNotEmpty) 'warehouse_id': warehouseId,
    };
    final uri = Uri.parse('$baseUrl/api/v1/seller/products').replace(queryParameters: query);
    final response = await http.get(uri, headers: _authHeaders);
    return _decode(response);
  }

  static Future<List<Map<String, dynamic>>> fetchWarehouses() async {
    final data = await _authGet('/api/v1/seller/warehouses');
    return List<Map<String, dynamic>>.from(data['warehouses'] ?? []);
  }

  static Future<Map<String, dynamic>> fetchSellerOrders({
    String status = 'all',
    bool mine = true,
    int page = 1,
    int perPage = 50,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/seller/orders').replace(queryParameters: {
      'status': status,
      'mine': '$mine',
      'page': '$page',
      'per_page': '$perPage',
    });
    final response = await http.get(uri, headers: _authHeaders);
    return _decode(response);
  }

  static Future<Map<String, dynamic>> createSellerOrder({
    String clientId = '',
    required String clientName,
    String clientRif = '',
    String clientEmail = '',
    required String warehouseId,
    required String docType,
    String comment = '',
    required List<Map<String, dynamic>> items,
  }) async {
    return _authPost('/api/v1/seller/orders', {
      'client_id': clientId,
      'client_name': clientName,
      'client_rif': clientRif,
      'client_email': clientEmail,
      'warehouse_id': warehouseId,
      'doc_type': docType,
      'comment': comment,
      'items': items,
    });
  }

  static Future<Map<String, dynamic>> fetchOrderDetail(String orderId) async {
    final data = await _authGet('/api/v1/seller/orders/$orderId');
    return Map<String, dynamic>.from(data['order'] ?? {});
  }

  static Future<void> cancelOrder(String orderId, {String reason = ''}) async {
    await _authPost('/api/v1/seller/orders/$orderId/cancel', {'reason': reason});
  }

  static Future<Map<String, dynamic>> fetchSellerBudgets({int page = 1, int perPage = 50}) async {
    final uri = Uri.parse('$baseUrl/api/v1/seller/budgets').replace(queryParameters: {
      'page': '$page',
      'per_page': '$perPage',
    });
    final response = await http.get(uri, headers: _authHeaders);
    return _decode(response);
  }

  static Future<Map<String, dynamic>> createSellerBudget({
    String clientId = '',
    required String clientName,
    String clientRif = '',
    String comment = '',
    required List<Map<String, dynamic>> items,
  }) async {
    return _authPost('/api/v1/seller/budgets', {
      'client_id': clientId,
      'client_name': clientName,
      'client_rif': clientRif,
      'comment': comment,
      'items': items,
    });
  }

  static Future<Map<String, dynamic>> convertBudget(
    String budgetId, {
    required String warehouseId,
    required String docType,
  }) async {
    return _authPost('/api/v1/seller/budgets/$budgetId/convert', {
      'warehouse_id': warehouseId,
      'doc_type': docType,
    });
  }

  static Future<List<Map<String, dynamic>>> fetchAccountsReceivable() async {
    final data = await _authGet('/api/v1/seller/accounts-receivable');
    return List<Map<String, dynamic>>.from(data['receivables'] ?? []);
  }

  /// Cuentas por Cobrar a nivel de factura con antigüedad de saldo. Por
  /// defecto solo trae las facturas del vendedor autenticado.
  static Future<Map<String, dynamic>> fetchSellerReceivables({
    String search = '',
    String bucket = '',
    bool mine = true,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/seller/receivables').replace(queryParameters: {
      'mine': '$mine',
      if (search.isNotEmpty) 'search': search,
      if (bucket.isNotEmpty) 'bucket': bucket,
    });
    final response = await http.get(uri, headers: _authHeaders);
    return _decode(response);
  }

  static Future<void> registerReceivablePayment({
    required String invoiceId,
    required double amount,
    String paymentMethod = 'Efectivo',
    String reference = '',
    String notes = '',
  }) async {
    await _authPost('/api/v1/seller/receivables/payment', {
      'invoice_id': invoiceId,
      'amount': amount,
      'payment_method': paymentMethod,
      'reference': reference,
      'notes': notes,
    });
  }

  static Future<List<Map<String, dynamic>>> fetchReceivablePayments(String invoiceId) async {
    final data = await _authGet('/api/v1/seller/receivables/invoice/$invoiceId/payments');
    return List<Map<String, dynamic>>.from(data['payments'] ?? []);
  }
}
