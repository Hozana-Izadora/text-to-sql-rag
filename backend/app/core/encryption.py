"""Criptografia simétrica das credenciais de banco das conexões cadastradas.

Usa Fernet (AES-128-CBC + HMAC-SHA256) — criptografia reversível, não hashing:
a senha original precisa ser recuperada para abrir a conexão com o banco do usuário.
"""

from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import settings

_MISSING_KEY_MESSAGE = (
    "ENCRYPTION_SECRET_KEY não configurada. Gere uma chave e coloque no .env:\n"
    "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
)


class CredentialEncryptor:
    """Encripta/decripta strings com uma chave Fernet vinda do ambiente."""

    def __init__(self, secret_key: str) -> None:
        if not secret_key:
            raise RuntimeError(_MISSING_KEY_MESSAGE)
        # Fernet valida o formato da chave (32 bytes url-safe base64) aqui e
        # levanta ValueError com mensagem clara se a chave estiver malformada.
        self._fernet = Fernet(secret_key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()


@lru_cache
def get_encryptor() -> CredentialEncryptor:
    """Singleton por processo. Overridable em testes via monkeypatch."""
    return CredentialEncryptor(settings.encryption_secret_key)
