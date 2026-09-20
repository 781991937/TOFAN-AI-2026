# TOFAN Authentication

## Sign-in methods

TOFAN can support Google OAuth, email/password, phone OTP, and passkeys/device
biometrics.

## Biometric design

A fingerprint or face scan is performed by the user's device. TOFAN does not
receive or store the user's biometric template.

Flow:

1. User signs in with Google, phone OTP, or email/password.
2. User chooses Enable biometric login.
3. The device creates or unlocks a passkey using its secure biometric system.
4. TOFAN stores credential metadata and public-key information.
5. On later sign-in, the device verifies the biometric locally.
6. The device signs the server authentication challenge.
7. TOFAN verifies the signed challenge and creates the session.

## Security requirements

- Never store raw fingerprints, face templates, or biometric images.
- Never trust a client-side biometric flag as proof of identity.
- Bind credentials to a specific user and device.
- Verify challenges server-side and prevent replay.
- Track signature counters where supported.
- Allow users to revoke individual devices.
- Audit registration, authentication, revocation, and failures.
- Require normal account authorization before registering a new credential.
- Use a standards-compliant WebAuthn/passkey library; do not implement custom
  cryptography.

## Recovery

Biometric login is an additional authentication method. Users retain a
registered Google account, phone OTP, or email/password recovery path.


## Session security
Sessions use random opaque bearer tokens; only SHA-256 token digests are persisted. OTP codes are HMAC-protected with `AUTH_OTP_PEPPER` and are rate-limited by challenge attempt count.
