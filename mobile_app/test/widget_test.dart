import 'package:flutter_test/flutter_test.dart';

import 'package:gestion_360/main.dart';

void main() {
  testWidgets('App arranca en la vitrina pública (Guest Browsing)', (WidgetTester tester) async {
    await tester.pumpWidget(const Gestion360App());

    // Se muestra la barra superior con el nombre de la app sin requerir login.
    expect(find.text('Gestión 360'), findsOneWidget);
    expect(find.text('Encuentra lo que buscas'), findsOneWidget);
  });
}
