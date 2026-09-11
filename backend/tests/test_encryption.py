import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.encryption import CredentialEncryptor


def test_encrypt_then_decrypt_roundtrips() -> None:
    encryptor = CredentialEncryptor(Fernet.generate_key().decode())

    ciphertext = encryptor.encrypt("s3nh4-do-banco")

    assert ciphertext != "s3nh4-do-banco"
    assert encryptor.decrypt(ciphertext) == "s3nh4-do-banco"


def test_decrypt_with_wrong_key_fails() -> None:
    ciphertext = CredentialEncryptor(Fernet.generate_key().decode()).encrypt("segredo")

    other = CredentialEncryptor(Fernet.generate_key().decode())

    with pytest.raises(InvalidToken):
        other.decrypt(ciphertext)


def test_missing_key_raises_with_guidance() -> None:
    with pytest.raises(RuntimeError, match="ENCRYPTION_SECRET_KEY"):
        CredentialEncryptor("")
