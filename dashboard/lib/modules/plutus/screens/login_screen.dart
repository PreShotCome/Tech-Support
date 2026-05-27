import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../main.dart';
import '../services/auth_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with SingleTickerProviderStateMixin {

  final _emailCtrl    = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _formKey      = GlobalKey<FormState>();
  bool _loading       = false;
  bool _obscure       = true;
  bool _isSignUp      = false;
  String? _error;

  late final AnimationController _fadeCtrl;
  late final Animation<double>   _fadeAnim;

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 900));
    _fadeAnim = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut);
    _fadeCtrl.forward();
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _emailAuth() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() { _loading = true; _error = null; });
    try {
      if (_isSignUp) {
        await AuthService.createAccount(_emailCtrl.text, _passwordCtrl.text);
      } else {
        await AuthService.signInWithEmail(_emailCtrl.text, _passwordCtrl.text);
      }
    } on FirebaseAuthException catch (e) {
      setState(() => _error = AuthService.friendlyError(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _googleAuth() async {
    setState(() { _loading = true; _error = null; });
    try {
      await AuthService.signInWithGoogle();
    } on FirebaseAuthException catch (e) {
      setState(() => _error = AuthService.friendlyError(e));
    } catch (_) {}
    finally { if (mounted) setState(() => _loading = false); }
  }

  // Apple sign-in is disabled for now (requires a paid Apple Developer
  // account). To re-enable: restore the Apple button in build() — it calls
  // AuthService.signInWithApple(), which is still in place.

  Future<void> _resetPassword() async {
    final email = _emailCtrl.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      setState(() => _error = 'Enter your email above, then tap reset.');
      return;
    }
    try {
      await AuthService.sendPasswordReset(email);
      if (mounted) {
        setState(() => _error = null);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Password reset email sent.'),
          backgroundColor: PC.green,
        ));
      }
    } on FirebaseAuthException catch (e) {
      setState(() => _error = AuthService.friendlyError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PC.background,
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnim,
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minHeight: MediaQuery.of(context).size.height -
                    MediaQuery.of(context).padding.vertical,
              ),
              child: IntrinsicHeight(child: Column(children: [
                const SizedBox(height: 64),

                // ── Brand ──────────────────────────────────────────────────
                Column(children: [
                  Container(
                    width: 90, height: 90,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(22),
                      boxShadow: [BoxShadow(
                        color: PC.pink.withOpacity(0.35),
                        blurRadius: 30, spreadRadius: 2,
                      )],
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(22),
                      child: Image.asset('assets/icon.png', fit: BoxFit.cover),
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text('PLUTUS', style: TextStyle(
                      color: PC.pink, fontSize: 28,
                      fontWeight: FontWeight.w300, letterSpacing: 10)),
                  const SizedBox(height: 6),
                  const Text('Grow wealth. Stay grounded.',
                      style: TextStyle(color: PC.sage, fontSize: 11, letterSpacing: 2)),
                ]),

                const SizedBox(height: 52),

                // ── Form ───────────────────────────────────────────────────
                Form(key: _formKey, child: Column(children: [
                  _field(_emailCtrl, 'EMAIL', Icons.alternate_email,
                      keyboardType: TextInputType.emailAddress,
                      validator: (v) => (v == null || !v.contains('@'))
                          ? 'Enter a valid email' : null),
                  const SizedBox(height: 16),
                  _field(_passwordCtrl, 'PASSWORD', Icons.lock_outline,
                      obscure: _obscure,
                      suffix: IconButton(
                        icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility,
                            color: PC.sage, size: 18),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                      validator: (v) => (v == null || v.length < 6)
                          ? 'At least 6 characters' : null),
                ])),

                const SizedBox(height: 20),

                if (_error != null) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.red.withOpacity(0.3)),
                    ),
                    child: Row(children: [
                      const Icon(Icons.error_outline, color: Colors.redAccent, size: 16),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_error!,
                          style: const TextStyle(color: Colors.redAccent, fontSize: 12))),
                    ]),
                  ),
                  const SizedBox(height: 16),
                ],

                SizedBox(
                  width: double.infinity, height: 52,
                  child: ElevatedButton(
                    onPressed: _loading ? null : _emailAuth,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: PC.pink,
                      foregroundColor: PC.background,
                      disabledBackgroundColor: PC.pink.withOpacity(0.4),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _loading
                        ? const SizedBox(width: 20, height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: PC.background))
                        : Text(_isSignUp ? 'CREATE ACCOUNT' : 'SIGN IN',
                            style: const TextStyle(
                                fontSize: 13, fontWeight: FontWeight.bold, letterSpacing: 3)),
                  ),
                ),

                if (!_isSignUp)
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: _loading ? null : _resetPassword,
                      child: const Text('Forgot password?',
                          style: TextStyle(color: PC.sage, fontSize: 12)),
                    ),
                  ),

                const SizedBox(height: 24),
                Row(children: [
                  Expanded(child: Divider(color: PC.grove)),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 16),
                    child: Text('OR', style: TextStyle(color: PC.sage, fontSize: 11, letterSpacing: 2)),
                  ),
                  Expanded(child: Divider(color: PC.grove)),
                ]),
                const SizedBox(height: 24),

                SizedBox(
                  width: double.infinity, height: 52,
                  child: OutlinedButton(
                    onPressed: _loading ? null : _googleAuth,
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: PC.grove, width: 1.5),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      backgroundColor: PC.surface.withOpacity(0.4),
                    ),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.g_mobiledata, color: Colors.white, size: 24),
                        SizedBox(width: 8),
                        Text('Continue with Google',
                            style: TextStyle(color: Colors.white, fontSize: 14)),
                      ],
                    ),
                  ),
                ),

                const Spacer(),

                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Text(_isSignUp ? 'Already have an account? ' : "Don't have an account? ",
                      style: const TextStyle(color: PC.sage, fontSize: 13)),
                  GestureDetector(
                    onTap: () => setState(() { _isSignUp = !_isSignUp; _error = null; }),
                    child: Text(_isSignUp ? 'Sign In' : 'Create Account',
                        style: const TextStyle(
                            color: PC.pink, fontSize: 13, fontWeight: FontWeight.bold)),
                  ),
                ]),
                const SizedBox(height: 32),
              ])),
            ),
          ),
        ),
      ),
    );
  }

  Widget _field(TextEditingController ctrl, String label, IconData icon, {
    bool obscure = false,
    Widget? suffix,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) => TextFormField(
    controller: ctrl,
    obscureText: obscure,
    keyboardType: keyboardType,
    style: const TextStyle(color: Colors.white, fontSize: 15),
    validator: validator,
    decoration: InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(color: PC.sage, fontSize: 11, letterSpacing: 2),
      prefixIcon: Icon(icon, color: PC.pink, size: 18),
      suffixIcon: suffix,
      enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: PC.grove, width: 1.5)),
      focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: PC.pink, width: 1.5)),
      errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.redAccent.withOpacity(0.7))),
      focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Colors.redAccent)),
      filled: true,
      fillColor: PC.surface.withOpacity(0.4),
    ),
  );
}
