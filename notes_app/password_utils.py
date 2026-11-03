import hashlib
import hmac
import secrets

ITERATIONS = 600000

# Protect new passwords
def generate_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_bytes = password.encode("utf-8")

    hashed_password = hashlib.pbkdf2_hmac(
        "sha256",
        password_bytes,
        salt,
        ITERATIONS
    )

    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${hashed_password.hex()}"

# Check passwords during sign in
def check_password_hash(stored: str, password: str) -> bool:
    try:
        method, rounds, salt_text, expected_text = stored.split("$")

        if method != "pbkdf2_sha256":
            return False

        iteration_count = int(rounds)
        if iteration_count < 100000 or iteration_count > 2000000:
            return False

        salt = bytes.fromhex(salt_text)
        expected_hash = bytes.fromhex(expected_text)
        entered_password = password.encode("utf-8")

        entered_hash = hashlib.pbkdf2_hmac(
            "sha256",
            entered_password,
            salt,
            iteration_count
        )

        return hmac.compare_digest(entered_hash, expected_hash)

    except (ValueError, TypeError, AttributeError):
        return False
