import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:intl/intl.dart';

class ChatScreen extends StatefulWidget {
  final String userId;
  const ChatScreen({super.key, required this.userId});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  bool _sending = false;

  CollectionReference get _messages => FirebaseFirestore.instance
      .collection('conversations')
      .doc(widget.userId)
      .collection('messages');

  Future<void> _send() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() => _sending = true);
    _textController.clear();

    await _messages.add({
      'role': 'user',
      'content': text,
      'created_at': FieldValue.serverTimestamp(),
      'processed': false,
    });

    setState(() => _sending = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('TechSupport'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => FirebaseAuth.instance.signOut(),
            tooltip: 'Sign out',
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: StreamBuilder<QuerySnapshot>(
              stream: _messages.orderBy('created_at', descending: false).snapshots(),
              builder: (context, snapshot) {
                if (!snapshot.hasData) {
                  return const Center(child: CircularProgressIndicator());
                }
                final docs = snapshot.data!.docs;
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (_scrollController.hasClients) {
                    _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
                  }
                });
                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(12),
                  itemCount: docs.length,
                  itemBuilder: (context, i) => MessageBubble(doc: docs[i]),
                );
              },
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    decoration: const InputDecoration(
                      hintText: 'Type a message',
                      border: OutlineInputBorder(),
                    ),
                    minLines: 1,
                    maxLines: 5,
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: _sending ? null : _send,
                  icon: const Icon(Icons.send),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class MessageBubble extends StatelessWidget {
  final QueryDocumentSnapshot doc;
  const MessageBubble({super.key, required this.doc});

  @override
  Widget build(BuildContext context) {
    final data = doc.data() as Map<String, dynamic>;
    final role = (data['role'] ?? 'user') as String;
    final content = (data['content'] ?? '') as String;
    final ts = data['created_at'] is Timestamp ? (data['created_at'] as Timestamp).toDate() : null;
    final isUser = role == 'user';
    final color = isUser ? Theme.of(context).colorScheme.primary : Theme.of(context).colorScheme.surfaceVariant;
    final textColor = isUser ? Theme.of(context).colorScheme.onPrimary : Theme.of(context).colorScheme.onSurface;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SelectableText(content, style: TextStyle(color: textColor, fontSize: 15)),
              if (ts != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    DateFormat.Hm().format(ts),
                    style: TextStyle(color: textColor.withOpacity(0.6), fontSize: 11),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
