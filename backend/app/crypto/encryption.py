import json
import os
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from app.config import settings


def derive_tenant_key(tenant_id: uuid.UUID) -> bytes:
    master_key = bytes.fromhex(settings.master_key)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=tenant_id.bytes,
        info=b"gainguard-credential-encryption",
    )
    return hkdf.derive(master_key)


def encrypt_credentials(tenant_id: uuid.UUID, credentials: dict) -> bytes:
    key = derive_tenant_key(tenant_id)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    plaintext = json.dumps(credentials).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext  # 12-byte nonce prepended


def decrypt_credentials(tenant_id: uuid.UUID, data: bytes) -> dict:
    key = derive_tenant_key(tenant_id)
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext)
