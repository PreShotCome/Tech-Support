// Chat service — wraps the Firestore conversation collection used by
// the Python bridge. Single source of truth for the path layout:
//   conversations/{userId}/messages/{messageId}
// with fields {role, content, created_at, processed}.

import 'package:cloud_firestore/cloud_firestore.dart';

class ChatService {
  final String userId;
  ChatService(this.userId);

  CollectionReference<Map<String, dynamic>> get messages => FirebaseFirestore
      .instance
      .collection('conversations')
      .doc(userId)
      .collection('messages');

  Stream<QuerySnapshot<Map<String, dynamic>>> stream() {
    return messages.orderBy('created_at', descending: false).snapshots();
  }

  Future<void> sendUserMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    await messages.add({
      'role': 'user',
      'content': trimmed,
      'created_at': FieldValue.serverTimestamp(),
      'processed': false,
    });
  }
}
