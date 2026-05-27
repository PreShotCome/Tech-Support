// Firebase project options for each module. Each module's Firebase project is
// registered as a named app in main.dart so per-app Firestore streams, auth
// state, and ID tokens remain isolated.
//
// Trading-Bot's woohoo-ad450 is the DEFAULT app because FirebaseMessaging
// is hardcoded to the default app on Android, and Trading-Bot is the only
// module that uses push notifications.

import 'package:firebase_core/firebase_core.dart';

// woohoo-ad450 — DEFAULT app (Trading-Bot / Proteus)
const FirebaseOptions tradingBotOptions = FirebaseOptions(
  apiKey:            'AIzaSyAsTpJicpzwC-zSbQZGMnvmR_GvzMbtyPU',
  appId:             '1:71678603306:android:9c2fb8bdb043f008d95353',
  messagingSenderId: '71678603306',
  projectId:         'woohoo-ad450',
  storageBucket:     'woohoo-ad450.firebasestorage.app',
);

// plutus-f7e90 — Plutus (named app 'plutus')
const FirebaseOptions plutusOptions = FirebaseOptions(
  apiKey:            'AIzaSyCD936wn1_p9MSrkSrpS-5Xb2hfbvBltaM',
  appId:             '1:404917497662:android:e6c14a8c8a0f1c16c1466f',
  messagingSenderId: '404917497662',
  projectId:         'plutus-f7e90',
  storageBucket:     'plutus-f7e90.firebasestorage.app',
);

// data-55089 — Tech-Support / Theo (named app 'theo')
// NOTE: original flutter_app had only WEB options. Android appId here is
// the web appId — user should replace with the Android appId from the
// Firebase console (Project Settings → Add Android app, package
// com.preshotcome.dashboard) before first build, or it will fail to init.
const FirebaseOptions theoOptions = FirebaseOptions(
  apiKey:            'AIzaSyBlD7IycQc2Koxtga7tCnVZLWU8zYgSZEM',
  appId:             '1:174078660867:web:7dab877b804d4a61069936',
  messagingSenderId: '174078660867',
  projectId:         'data-55089',
  storageBucket:     'data-55089.firebasestorage.app',
);

// hestia-fbc49 — Hestia (named app 'hestia')
const FirebaseOptions hestiaOptions = FirebaseOptions(
  apiKey:            'AIzaSyAnZ3sLf8k7XERUawLtuN9al6qviaBGfTU',
  appId:             '1:683887454101:web:c894335b6b2cf155b6789c',
  messagingSenderId: '683887454101',
  projectId:         'hestia-fbc49',
  storageBucket:     'hestia-fbc49.firebasestorage.app',
);
