// Web implementation: open the brain visualization in a new browser tab.
// Imported only when dart.library.html is available (Flutter web).
// See brain_launcher_stub.dart for the non-web no-op.

// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

void openBrain() {
  html.window.open('/brain.html', '_blank');
}
