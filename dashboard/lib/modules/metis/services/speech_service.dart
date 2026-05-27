import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Thin wrapper over device speech recognition for tap-to-record capture.
class SpeechService {
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _initialized = false;
  void Function()? _onDone;

  bool get isListening => _speech.isListening;

  Future<bool> _ensureInit() async {
    if (_initialized) return true;
    _initialized = await _speech.initialize(
      onError: (_) => _onDone?.call(),
      onStatus: (status) {
        if (status == 'done' || status == 'notListening') _onDone?.call();
      },
    );
    return _initialized;
  }

  /// Starts a listening session. [onResult] fires with interim and final
  /// transcripts; [onDone] fires once when recognition stops.
  Future<bool> start({
    required void Function(String text, bool isFinal) onResult,
    required void Function() onDone,
  }) async {
    _onDone = onDone;
    if (!await _ensureInit()) return false;

    await _speech.listen(
      onResult: (r) => onResult(r.recognizedWords, r.finalResult),
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 4),
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
      ),
    );
    return true;
  }

  Future<void> stop() async {
    _onDone = null;
    if (_speech.isListening) await _speech.stop();
  }

  Future<void> cancel() async {
    _onDone = null;
    if (_speech.isListening) await _speech.cancel();
  }
}

final speechService = SpeechService();
