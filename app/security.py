"""app.security — Argon2id password hashing + opaque session-cookie policy (Phase 3 T2 auth).

Closure-gap 2 (PHASE0.md): argon2-cffi was MISSING and had to be added + pinned.
This module is the single home of password hashing and the session-cookie attribute
policy, and the ONLY place we touch the real argon2-cffi library:

  * hash_password() / verify_password() wrap ``argon2.PasswordHasher`` with the
    EXACT parameters gate C2 specifies (Argon2id, m=19 MiB, t=2, p=1) — we never
    re-invent an encoder (test_mqtt_packet anti-pattern): verification always
    delegates to the real argon2 library.
  * SESSION_COOKIE attributes: HttpOnly + Secure + SameSite=Lax + opaque value,
    per PHASE0.md §P Phase 3 gate C2.

One concern: crypto primitives + cookie policy. Session storage/lifecycle lives in
app/auth_service.py; the HTTP routes live in app/routers/auth.py.
"""
from __future__ import annotations

from argon2 import PasswordHasher, exceptions

# Gate C2 Argon2id parameters (PHASE0-map / OWASP): 19 MiB, t=2, p=1.
MEMORY_KIB = 19 * 1024  # 19 MiB, expressed in KiB
TIME_COST = 2
PARALLELISM = 1

_ph = PasswordHasher(time_cost=TIME_COST, memory_cost=MEMORY_KIB,
                     parallelism=PARALLELISM)

# F3 timing-equalizer (audit 1188): a fixed dummy hash generated at import from a
# fixed dummy string. authenticate() runs a real argon2 verify against this when
# the username does not exist, so unknown-username responses cost the same CPU
# work as existing-username ones (no enumeration-by-timing oracle).
DUMMY_PASSWORD = "matapp-dummy-credential-for-timing-equalizer"
DUMMY_HASH = _ph.hash(DUMMY_PASSWORD)

# Opaque session cookie policy (PHASE0.md §P Phase 3).
SESSION_COOKIE = "matapp_session"
SESSION_HTTPONLY = True
SESSION_SECURE = True
SESSION_SAMESITE = "lax"


def hash_password(plain: str) -> str:
    """Hash a plaintext password with Argon2id (19 MiB / t=2 / p=1).

    Returns the argon2 PHC-encoded string (``$argon2id$v=19$...``) safe to store
    in the ``users.password_hash`` column.
    """
    return _ph.hash(plain)


def verify_password(plain: str, encoded: str) -> bool:
    """Return True iff *plain* matches the stored Argon2id hash *encoded*.

    Delegates to the real argon2-cffi verifier — we never implement our own
    comparison (anti-mqtt_packet). Any mismatch/error returns False.
    """
    try:
        return _ph.verify(encoded, plain)
    except (exceptions.VerificationError, exceptions.InvalidHashError):
        return False
