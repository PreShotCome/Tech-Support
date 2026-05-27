import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../services/auth_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with SingleTickerProviderStateMixin {

  // ── State ──────────────────────────────────────────────────────────────────
  final _emailCtrl    = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _formKey      = GlobalKey<FormState>();

  bool   _loading       = false;
  bool   _obscure       = true;
  bool   _isSignUp      = false;
  String? _error;

  late final AnimationController _fadeCtrl;
  late final Animation<double>   _fadeAnim;

  // ── Proteus colours ────────────────────────────────────────────────────────
  static const _bg       = Color(0xFF040A22);
  static const _surface  = Color(0xFF0B1A6B);
  static const _gold     = Color(0xFFC9A227);
  static const _goldBrt  = Color(0xFFF0C040);
  static const _steel    = Color(0xFFB0C4DE);

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 900));
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

  // ── Actions ────────────────────────────────────────────────────────────────

  Future<void> _emailAuth() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() { _loading = true; _error = null; });
    try {
      if (_isSignUp) {
        await AuthService.createAccount(_emailCtrl.text, _passwordCtrl.text);
      } else {
        await AuthService.signInWithEmail(_emailCtrl.text, _passwordCtrl.text);
      }
      // AuthWrapper will handle navigation automatically via stream
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
    } catch (_) {
      // User cancelled — no error shown
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _forgotPassword() async {
    final email = _emailCtrl.text.trim();
    if (email.isEmpty) {
      setState(() => _error = 'Enter your email above first.');
      return;
    }
    await AuthService.sendPasswordReset(email);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Password reset email sent.'),
        backgroundColor: Color(0xFF0F2485),
      ));
    }
  }

  // ── UI ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnim,
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minHeight: MediaQuery.of(context).size.height -
                    MediaQuery.of(context).padding.top -
                    MediaQuery.of(context).padding.bottom,
              ),
              child: IntrinsicHeight(
                child: Column(
                  children: [
                    const SizedBox(height: 60),

                    // ── Branding ────────────────────────────────────────────
                    _buildBrand(),

                    const SizedBox(height: 52),

                    // ── Form ────────────────────────────────────────────────
                    Form(
                      key: _formKey,
                      child: Column(children: [

                        _inputField(
                          controller: _emailCtrl,
                          label: 'EMAIL',
                          icon: Icons.alternate_email,
                          keyboardType: TextInputType.emailAddress,
                          validator: (v) =>
                              (v == null || !v.contains('@'))
                                  ? 'Enter a valid email'
                                  : null,
                        ),
                        const SizedBox(height: 16),

                        _inputField(
                          controller: _passwordCtrl,
                          label: 'PASSWORD',
                          icon: Icons.lock_outline,
                          obscure: _obscure,
                          suffix: IconButton(
                            icon: Icon(
                              _obscure ? Icons.visibility_off : Icons.visibility,
                              color: _steel, size: 18,
                            ),
                            onPressed: () => setState(() => _obscure = !_obscure),
                          ),
                          validator: (v) =>
                              (v == null || v.length < 6)
                                  ? 'At least 6 characters'
                                  : null,
                        ),
                      ]),
                    ),

                    // ── Forgot password ─────────────────────────────────────
                    if (!_isSignUp) ...[
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                          onPressed: _loading ? null : _forgotPassword,
                          child: const Text('Forgot password?',
                              style: TextStyle(color: _steel, fontSize: 12)),
                        ),
                      ),
                    ] else
                      const SizedBox(height: 20),

                    // ── Error message ───────────────────────────────────────
                    if (_error != null) ...[
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: Colors.red.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: Colors.red.withOpacity(0.3)),
                        ),
                        child: Row(children: [
                          const Icon(Icons.error_outline,
                              color: Colors.redAccent, size: 16),
                          const SizedBox(width: 8),
                          Expanded(child: Text(_error!,
                              style: const TextStyle(
                                  color: Colors.redAccent, fontSize: 12))),
                        ]),
                      ),
                      const SizedBox(height: 12),
                    ],

                    const SizedBox(height: 8),

                    // ── Primary button ──────────────────────────────────────
                    _primaryButton(),

                    const SizedBox(height: 24),

                    // ── OR divider ──────────────────────────────────────────
                    _orDivider(),

                    const SizedBox(height: 24),

                    // ── Google button ───────────────────────────────────────
                    _googleButton(),

                    const Spacer(),

                    // ── Toggle sign-up / sign-in ────────────────────────────
                    _toggleMode(),

                    const SizedBox(height: 32),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  // ── Brand header ────────────────────────────────────────────────────────────

  Widget _buildBrand() {
    return Column(children: [
      // Icon
      Container(
        width: 90, height: 90,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          boxShadow: [
            BoxShadow(
              color: _gold.withOpacity(0.35),
              blurRadius: 30, spreadRadius: 2,
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(22),
          child: Image.asset('assets/icon.png', fit: BoxFit.cover),
        ),
      ),
      const SizedBox(height: 20),

      // Name
      const Text('PROTEUS',
          style: TextStyle(
            color: _gold,
            fontSize: 28,
            fontWeight: FontWeight.w300,
            letterSpacing: 10,
          )),
      const SizedBox(height: 6),

      // Tagline
      const Text('Change form. Never change course.',
          style: TextStyle(
            color: _steel,
            fontSize: 11,
            letterSpacing: 2,
          )),
    ]);
  }

  // ── Input field ─────────────────────────────────────────────────────────────

  Widget _inputField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    bool obscure = false,
    Widget? suffix,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: obscure,
      keyboardType: keyboardType,
      style: const TextStyle(color: Colors.white, fontSize: 15),
      validator: validator,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(
            color: _steel, fontSize: 11, letterSpacing: 2),
        prefixIcon: Icon(icon, color: _gold, size: 18),
        suffixIcon: suffix,
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: _surface, width: 1.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: _gold, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.redAccent.withOpacity(0.7)),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Colors.redAccent),
        ),
        filled: true,
        fillColor: _surface.withOpacity(0.4),
      ),
    );
  }

  // ── Primary button ──────────────────────────────────────────────────────────

  Widget _primaryButton() {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: _loading ? null : _emailAuth,
        style: ElevatedButton.styleFrom(
          backgroundColor: _gold,
          foregroundColor: const Color(0xFF040A22),
          disabledBackgroundColor: _gold.withOpacity(0.4),
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12)),
          elevation: 0,
        ),
        child: _loading
            ? const SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(
                    strokeWidth: 2, color: Color(0xFF040A22)))
            : Text(
                _isSignUp ? 'CREATE ACCOUNT' : 'SIGN IN',
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 3,
                ),
              ),
      ),
    );
  }

  // ── OR divider ───────────────────────────────────────────────────────────────

  Widget _orDivider() {
    return Row(children: [
      Expanded(child: Divider(color: _surface, thickness: 1)),
      const Padding(
        padding: EdgeInsets.symmetric(horizontal: 16),
        child: Text('OR', style: TextStyle(
            color: _steel, fontSize: 11, letterSpacing: 2)),
      ),
      Expanded(child: Divider(color: _surface, thickness: 1)),
    ]);
  }

  // ── Google button ────────────────────────────────────────────────────────────

  Widget _googleButton() {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: OutlinedButton(
        onPressed: _loading ? null : _googleAuth,
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: _surface, width: 1.5),
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12)),
          backgroundColor: _surface.withOpacity(0.3),
        ),
        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          // Google G logo (coloured circles)
          _googleLogo(),
          const SizedBox(width: 12),
          const Text('Continue with Google',
              style: TextStyle(
                color: Colors.white,
                fontSize: 14,
                letterSpacing: 0.5,
              )),
        ]),
      ),
    );
  }

  Widget _googleLogo() {
    return SizedBox(
      width: 20, height: 20,
      child: CustomPaint(painter: _GoogleLogoPainter()),
    );
  }

  // ── Toggle mode ──────────────────────────────────────────────────────────────

  Widget _toggleMode() {
    return Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      Text(
        _isSignUp ? 'Already have an account? ' : "Don't have an account? ",
        style: const TextStyle(color: _steel, fontSize: 13),
      ),
      GestureDetector(
        onTap: () => setState(() {
          _isSignUp = !_isSignUp;
          _error = null;
        }),
        child: Text(
          _isSignUp ? 'Sign In' : 'Create Account',
          style: const TextStyle(
            color: _gold,
            fontSize: 13,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    ]);
  }
}

// ── Google logo painter ──────────────────────────────────────────────────────

class _GoogleLogoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final r  = size.width / 2;

    // Draw a simple coloured G-ring approximation
    final colors = [
      const Color(0xFF4285F4), // blue
      const Color(0xFF34A853), // green
      const Color(0xFFFBBC05), // yellow
      const Color(0xFFEA4335), // red
    ];
    final paint = Paint()..style = PaintingStyle.stroke..strokeWidth = 3;
    for (int i = 0; i < 4; i++) {
      paint.color = colors[i];
      canvas.drawArc(
        Rect.fromCircle(center: Offset(cx, cy), radius: r - 1.5),
        (i * 3.14159 / 2) - 0.3,
        3.14159 / 2 + 0.3,
        false,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_) => false;
}
