// Login screen. Anonymous tap-to-continue as default (fastest entry);
// email/password collapsed behind an expansion tile so the basic flow
// stays one button. Google / Apple wired into AuthService stubs.

import 'package:flutter/material.dart';

import '../main.dart';            // TS palette
import '../services/auth_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _busy = false;
  bool _signingUp = false;

  Future<void> _continueAnon() async {
    setState(() => _busy = true);
    try {
      await AuthService.signInAnonymously();
    } catch (e) {
      _toast(AuthService.friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submitEmail() async {
    final email = _emailController.text;
    final pw = _passwordController.text;
    if (email.isEmpty || pw.isEmpty) {
      _toast('Email and password required.');
      return;
    }
    setState(() => _busy = true);
    try {
      if (_signingUp) {
        await AuthService.signUpWithEmail(email, pw);
      } else {
        await AuthService.signInWithEmail(email, pw);
      }
    } catch (e) {
      _toast(AuthService.friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 28),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'TechSupport',
                    style: TextStyle(fontSize: 30, fontWeight: FontWeight.w300, letterSpacing: 2),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'a long-term thinking partner',
                    style: TextStyle(color: TS.sage, fontSize: 13),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 40),
                  FilledButton.icon(
                    onPressed: _busy ? null : _continueAnon,
                    icon: const Icon(Icons.arrow_forward),
                    label: const Text('Continue'),
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Theme(
                    data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      childrenPadding: EdgeInsets.zero,
                      title: const Text(
                        'Use email instead',
                        style: TextStyle(color: TS.sage, fontSize: 13),
                      ),
                      children: [
                        const SizedBox(height: 8),
                        TextField(
                          controller: _emailController,
                          enabled: !_busy,
                          keyboardType: TextInputType.emailAddress,
                          autofillHints: const [AutofillHints.email],
                          decoration: const InputDecoration(labelText: 'Email'),
                        ),
                        const SizedBox(height: 10),
                        TextField(
                          controller: _passwordController,
                          enabled: !_busy,
                          obscureText: true,
                          autofillHints: const [AutofillHints.password],
                          decoration: const InputDecoration(labelText: 'Password'),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            TextButton(
                              onPressed: _busy
                                  ? null
                                  : () => setState(() => _signingUp = !_signingUp),
                              child: Text(
                                _signingUp ? 'Have an account? Sign in' : 'New here? Sign up',
                                style: const TextStyle(color: TS.accent),
                              ),
                            ),
                            FilledButton(
                              onPressed: _busy ? null : _submitEmail,
                              child: Text(_signingUp ? 'Sign up' : 'Sign in'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  if (_busy)
                    const Padding(
                      padding: EdgeInsets.only(top: 24),
                      child: Center(child: CircularProgressIndicator(color: TS.accent)),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
