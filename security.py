
import hashlib
import secrets


def gerar_chave_api() -> str:
    """Gera uma chave aleatória para um sistema cliente."""
    return secrets.token_urlsafe(32)


def calcular_hash_chave(chave: str) -> str:
    """Retorna o hash SHA-256 da chave recebida."""
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()
