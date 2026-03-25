import uuid
import pytest
from app.crypto.encryption import derive_tenant_key, encrypt_credentials, decrypt_credentials

def test_derive_tenant_key_deterministic():
    tenant_id = uuid.uuid4()
    key1 = derive_tenant_key(tenant_id)
    key2 = derive_tenant_key(tenant_id)
    assert key1 == key2

def test_derive_tenant_key_unique_per_tenant():
    key1 = derive_tenant_key(uuid.uuid4())
    key2 = derive_tenant_key(uuid.uuid4())
    assert key1 != key2

def test_encrypt_decrypt_roundtrip():
    tenant_id = uuid.uuid4()
    credentials = {"api_key": "abc123", "secret": "xyz789"}
    encrypted = encrypt_credentials(tenant_id, credentials)
    assert isinstance(encrypted, bytes)
    decrypted = decrypt_credentials(tenant_id, encrypted)
    assert decrypted == credentials

def test_decrypt_with_wrong_tenant_fails():
    tenant_id_a = uuid.uuid4()
    tenant_id_b = uuid.uuid4()
    encrypted = encrypt_credentials(tenant_id_a, {"key": "val"})
    with pytest.raises(Exception):
        decrypt_credentials(tenant_id_b, encrypted)
