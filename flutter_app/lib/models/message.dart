// Message model — plain Dart class, plutus convention (no codegen,
// no freezed). Construct from a Firestore doc; do not extend Equatable.

import 'package:cloud_firestore/cloud_firestore.dart';

class Message {
  final String id;
  final String role;        // 'user' | 'assistant'
  final String content;
  final DateTime? createdAt;
  final bool processed;

  const Message({
    required this.id,
    required this.role,
    required this.content,
    required this.createdAt,
    required this.processed,
  });

  factory Message.fromDoc(QueryDocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data();
    final ts = data['created_at'];
    return Message(
      id: doc.id,
      role: (data['role'] ?? 'user') as String,
      content: (data['content'] ?? '') as String,
      createdAt: ts is Timestamp ? ts.toDate() : null,
      processed: (data['processed'] ?? false) as bool,
    );
  }

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';
}
