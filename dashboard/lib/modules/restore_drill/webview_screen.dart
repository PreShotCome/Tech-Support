// Restore-Drill is a PWA, so we host it in a webview tile rather than port
// it natively. Replace _kUrl with the deployed PWA URL.

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

const String _kUrl = 'https://restore-drill.example.com';

class RestoreDrillWebView extends StatefulWidget {
  const RestoreDrillWebView({super.key});

  @override
  State<RestoreDrillWebView> createState() => _RestoreDrillWebViewState();
}

class _RestoreDrillWebViewState extends State<RestoreDrillWebView> {
  late final WebViewController _controller;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..loadRequest(Uri.parse(_kUrl));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('RESTORE DRILL')),
      body: WebViewWidget(controller: _controller),
    );
  }
}
