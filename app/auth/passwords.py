"""Password hashing utilities using the Python standard library."""
import base64, hashlib, hmac, os
_N, _R, _P, _DKLEN = 2**14, 8, 1, 32
def hash_password(password: str) -> str:
    if len(password) < 8: raise ValueError("Password must contain at least 8 characters.")
    salt=os.urandom(16); digest=hashlib.scrypt(password.encode(),salt=salt,n=_N,r=_R,p=_P,dklen=_DKLEN)
    return "scrypt$" + str(_N) + "$" + str(_R) + "$" + str(_P) + "$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()
def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm,n,r,p,salt_b64,digest_b64=encoded.split("$",5)
        if algorithm!="scrypt": return False
        expected=base64.b64decode(digest_b64)
        actual=hashlib.scrypt(password.encode(),salt=base64.b64decode(salt_b64),n=int(n),r=int(r),p=int(p),dklen=len(expected))
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError): return False
