import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';
import '../models/reminder.dart';

/// On-device SQLite store for reminders. No cloud account, no sync.
class AppDatabase {
  static const _file = 'metis.db';
  static const _table = 'reminders';

  Database? _db;

  Future<Database> get _database async {
    return _db ??= await _open();
  }

  Future<Database> _open() async {
    final dir = await getDatabasesPath();
    return openDatabase(
      p.join(dir, _file),
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE $_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            due_at INTEGER NOT NULL,
            has_time INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL DEFAULT 'text',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            raw_input TEXT NOT NULL DEFAULT ''
          )
        ''');
      },
    );
  }

  Future<List<Reminder>> all() async {
    final db = await _database;
    final rows = await db.query(_table, orderBy: 'due_at ASC');
    return rows.map(Reminder.fromMap).toList();
  }

  Future<int> insert(Reminder r) async {
    final db = await _database;
    final map = r.toMap()..remove('id');
    return db.insert(_table, map);
  }

  Future<void> update(Reminder r) async {
    final db = await _database;
    await db.update(_table, r.toMap(), where: 'id = ?', whereArgs: [r.id]);
  }

  Future<void> delete(int id) async {
    final db = await _database;
    await db.delete(_table, where: 'id = ?', whereArgs: [id]);
  }
}
