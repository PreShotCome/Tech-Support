import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messages  = <_Msg>[];
  final _ctrl      = TextEditingController();
  final _scroll    = ScrollController();
  bool _thinking   = false;
  int _autonomy    = 1;

  @override
  void initState() {
    super.initState();
    _messages.add(_Msg(
      text: "Hello! I'm your AI trading assistant.\n\n"
            "I have access to your live portfolio, trade history, and market signals.\n\n"
            "Ask me anything — 'What should I buy right now?', "
            "'How is TSLA looking?', 'Analyze my portfolio risk.' — I'm here to help.\n\n"
            "⚠️ Connect your Anthropic API key on the server to activate full AI analysis.",
      isBot: true,
    ));
  }

  Future<void> _send() async {
    final text = _ctrl.text.trim();
    if (text.isEmpty || _thinking) return;
    _ctrl.clear();
    setState(() {
      _messages.add(_Msg(text: text, isBot: false));
      _thinking = true;
    });
    _scrollDown();

    try {
      final reply = await ApiService.chat(text, _autonomy);
      setState(() {
        _messages.add(_Msg(text: reply, isBot: true));
        _thinking = false;
      });
    } catch (e) {
      setState(() {
        _messages.add(_Msg(text: 'Error: $e', isBot: true, isError: true));
        _thinking = false;
      });
    }
    _scrollDown();
  }

  void _scrollDown() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0a0e1a),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0a0e1a),
        title: const Text('AI ADVISOR', style: TextStyle(
          color: Color(0xFF90a4ae), letterSpacing: 3, fontSize: 13)),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: _autonomyPill(),
          ),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.all(16),
            itemCount: _messages.length + (_thinking ? 1 : 0),
            itemBuilder: (ctx, i) {
              if (_thinking && i == _messages.length) return _thinkingBubble();
              return _bubble(_messages[i]);
            },
          ),
        ),
        _inputBar(),
      ]),
    );
  }

  Widget _bubble(_Msg m) {
    final bg = m.isBot
        ? (m.isError ? Colors.red.withOpacity(0.15) : Colors.white.withOpacity(0.07))
        : const Color(0xFF4fc3f7).withOpacity(0.15);
    final align = m.isBot ? CrossAxisAlignment.start : CrossAxisAlignment.end;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(crossAxisAlignment: align, children: [
        Container(
          constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.82),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: m.isBot
                  ? (m.isError ? Colors.red.withOpacity(0.4) : Colors.white12)
                  : const Color(0xFF4fc3f7).withOpacity(0.4),
            ),
          ),
          child: Text(m.text, style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.5)),
        ),
      ]),
    );
  }

  Widget _thinkingBubble() => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.07),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white12),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        const SizedBox(
          width: 20, height: 20,
          child: CircularProgressIndicator(
            strokeWidth: 2, color: Color(0xFF4fc3f7)),
        ),
        const SizedBox(width: 10),
        const Text('Thinking...', style: TextStyle(color: Colors.white38, fontSize: 13)),
      ]),
    ),
  );

  Widget _inputBar() => Container(
    padding: const EdgeInsets.fromLTRB(16, 10, 16, 24),
    color: const Color(0xFF0d1120),
    child: Row(children: [
      Expanded(
        child: TextField(
          controller: _ctrl,
          style: const TextStyle(color: Colors.white),
          maxLines: null,
          onSubmitted: (_) => _send(),
          decoration: InputDecoration(
            hintText: 'Ask your AI advisor...',
            hintStyle: const TextStyle(color: Colors.white30),
            filled: true,
            fillColor: Colors.white10,
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
            contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          ),
        ),
      ),
      const SizedBox(width: 10),
      GestureDetector(
        onTap: _send,
        child: Container(
          width: 46, height: 46,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF4fc3f7), Color(0xFF0288d1)]),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
        ),
      ),
    ]),
  );

  Widget _autonomyPill() {
    final labels = ['👁', '💬', '⚡'];
    final colors = [Colors.blueGrey, const Color(0xFF4fc3f7), const Color(0xFFFFD700)];
    return GestureDetector(
      onTap: () => setState(() => _autonomy = (_autonomy + 1) % 3),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: colors[_autonomy].withOpacity(0.15),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: colors[_autonomy].withOpacity(0.5)),
        ),
        child: Text(labels[_autonomy],
            style: TextStyle(color: colors[_autonomy], fontSize: 16)),
      ),
    );
  }
}

class _Msg {
  final String text;
  final bool isBot;
  final bool isError;
  _Msg({required this.text, required this.isBot, this.isError = false});
}
