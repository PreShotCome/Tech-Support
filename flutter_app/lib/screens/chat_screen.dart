// Chat screen. Streams messages from Firestore via ChatService; sends
// new user messages with one method call. The bridge process fills in
// assistant responses asynchronously.

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../main.dart';            // TS palette
import '../models/message.dart';
import '../services/chat_service.dart';

class ChatScreen extends StatefulWidget {
  final String userId;
  const ChatScreen({super.key, required this.userId});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with WidgetsBindingObserver {
  late final ChatService _chat = ChatService(widget.userId);
  // Cache the stream subscription so build() doesn't re-create it on
  // every rebuild. Re-assigned on app-resume to force re-sync after
  // the browser/OS suspended JS while the PWA was backgrounded.
  late Stream<QuerySnapshot<Map<String, dynamic>>> _stream = _chat.stream();
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // When the PWA returns from background, re-subscribe to Firestore
    // so any messages that arrived while suspended show up.
    if (state == AppLifecycleState.resumed) {
      setState(() => _stream = _chat.stream());
    }
  }

  Future<void> _refresh() async {
    setState(() => _stream = _chat.stream());
    // Brief delay so the RefreshIndicator animation isn't snappy.
    await Future<void>.delayed(const Duration(milliseconds: 400));
  }

  // RefreshIndicator needs a scrollable child to detect pull gestures.
  // Wrap non-scrollable states (error / loading / empty) so pull-to-refresh
  // works from every screen, not just when there are messages.
  Widget _scrollable(Widget child) {
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: child,
        ),
      ),
    );
  }

  Future<void> _send() async {
    final text = _textController.text;
    if (text.trim().isEmpty || _sending) return;
    setState(() => _sending = true);
    _textController.clear();
    try {
      await _chat.sendUserMessage(text);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Send failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          Expanded(
            child: RefreshIndicator(
              color: TS.accent,
              onRefresh: _refresh,
              child: StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
                stream: _stream,
                builder: (context, snapshot) {
                  if (snapshot.hasError) {
                    return _scrollable(
                      Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Text(
                            'Firestore error: ${snapshot.error}',
                            style: const TextStyle(color: TS.danger),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      ),
                    );
                  }
                  if (!snapshot.hasData) {
                    return _scrollable(
                      const Center(
                        child: CircularProgressIndicator(color: TS.accent),
                      ),
                    );
                  }
                  final msgs = snapshot.data!.docs.map(Message.fromDoc).toList();
                  if (msgs.isEmpty) {
                    return _scrollable(const _EmptyState());
                  }
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (_scrollController.hasClients) {
                      _scrollController.jumpTo(
                        _scrollController.position.maxScrollExtent,
                      );
                    }
                  });
                  return ListView.builder(
                    controller: _scrollController,
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
                    itemCount: msgs.length,
                    itemBuilder: (context, i) => _Bubble(message: msgs[i]),
                  );
                },
              ),
            ),
          ),
          _Composer(
            controller: _textController,
            sending: _sending,
            onSend: _send,
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: const [
            Icon(Icons.mode_comment_outlined, color: TS.sage, size: 36),
            SizedBox(height: 12),
            Text(
              'No messages yet.',
              style: TextStyle(color: TS.sage, fontSize: 14),
            ),
            SizedBox(height: 4),
            Text(
              'Say something. The agent is listening on the other end.',
              style: TextStyle(color: TS.sage, fontSize: 12),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  final Message message;
  const _Bubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final bg = isUser ? TS.accent : TS.surface;
    final fg = isUser ? Colors.black : Colors.white;
    final subFg = isUser ? Colors.black.withOpacity(0.55) : TS.sage;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.80,
        ),
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(16),
              topRight: const Radius.circular(16),
              bottomLeft: Radius.circular(isUser ? 16 : 4),
              bottomRight: Radius.circular(isUser ? 4 : 16),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SelectableText(
                message.content,
                style: TextStyle(color: fg, fontSize: 15, height: 1.35),
              ),
              if (message.createdAt != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    DateFormat.Hm().format(message.createdAt!),
                    style: TextStyle(color: subFg, fontSize: 10.5),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;

  const _Composer({
    required this.controller,
    required this.sending,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: TS.background,
        border: Border(top: BorderSide(color: TS.surfaceAlt, width: 1)),
      ),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
      child: SafeArea(
        top: false,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                enabled: !sending,
                minLines: 1,
                maxLines: 6,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => onSend(),
                inputFormatters: [LengthLimitingTextInputFormatter(8000)],
                decoration: const InputDecoration(
                  hintText: 'Message…',
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: sending ? null : onSend,
              icon: sending
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.black,
                      ),
                    )
                  : const Icon(Icons.send),
            ),
          ],
        ),
      ),
    );
  }
}
