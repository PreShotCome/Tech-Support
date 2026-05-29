"""Theo additives — individually buildable, individually testable ideas.

Each module here is self-contained: stdlib-only where possible, no coupling
to the live agent loop, and its own runnable self-test under `__main__`.
The pattern is deliberate — an additive gets built and proven in isolation
first, then wired into the agent as a separate, deliberate step. That way a
half-finished idea can never destabilize Theo's live memory or voice.

Run any additive's self-test directly, e.g.:
    python -m agent.additives.hot_memory

Catalog + status lives in docs/additives.md.
"""
