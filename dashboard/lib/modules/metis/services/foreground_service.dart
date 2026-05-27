import 'dart:isolate';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';

/// Entry point for the background isolate. Must be a top-level function.
@pragma('vm:entry-point')
void startMetisCallback() {
  FlutterForegroundTask.setTaskHandler(_MetisTaskHandler());
}

/// Keeps the process resident so Metis stays ready to capture. The actual
/// capture is user-initiated (mic FAB); this handler just holds the service.
class _MetisTaskHandler extends TaskHandler {
  @override
  void onStart(DateTime timestamp, SendPort? sendPort) {}

  @override
  void onRepeatEvent(DateTime timestamp, SendPort? sendPort) {}

  @override
  void onDestroy(DateTime timestamp, SendPort? sendPort) {}
}

/// Controls the always-on foreground service: a persistent, low-priority
/// notification that keeps Metis alive and auto-restarts on device boot.
class ForegroundService {
  static void configure() {
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'metis_capture',
        channelName: 'Metis Capture Service',
        channelDescription: 'Keeps Metis ready to capture reminders.',
        priority: NotificationPriority.LOW,
      ),
      iosNotificationOptions: const IOSNotificationOptions(),
      foregroundTaskOptions: const ForegroundTaskOptions(
        interval: 900000,
        isOnceEvent: false,
        autoRunOnBoot: true,
        autoRunOnMyPackageReplaced: true,
        allowWakeLock: true,
        allowWifiLock: false,
      ),
    );
  }

  static Future<bool> isRunning() =>
      FlutterForegroundTask.isRunningService;

  static Future<void> start() async {
    if (await FlutterForegroundTask.isRunningService) return;
    await FlutterForegroundTask.startService(
      notificationTitle: 'Metis',
      notificationText: 'Always listening — never forgetting.',
      callback: startMetisCallback,
    );
  }

  static Future<void> stop() async {
    if (await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.stopService();
    }
  }
}
