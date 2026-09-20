import pytest

from app.auth.biometric import BiometricAuthError
from app.auth.webauthn import _validate_sign_count


def test_sign_count_accepts_authenticator_without_counter():
    assert _validate_sign_count(0, 0) == 0


def test_sign_count_advances_when_supported():
    assert _validate_sign_count(3, 4) == 4


@pytest.mark.parametrize(
    ("previous", "current"),
    [(3, 3), (3, 2), (3, 0)],
)
def test_sign_count_rejects_non_advancing_counter(previous, current):
    with pytest.raises(BiometricAuthError):
        _validate_sign_count(previous, current)
