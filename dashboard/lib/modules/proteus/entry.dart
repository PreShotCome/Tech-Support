// Proteus (Trading-Bot) module entry. Wraps the module's TradingBotApp.

import 'package:flutter/material.dart';
import 'main.dart' show TradingBotApp;

class ProteusEntry extends StatelessWidget {
  const ProteusEntry({super.key});
  @override
  Widget build(BuildContext context) => const TradingBotApp();
}
