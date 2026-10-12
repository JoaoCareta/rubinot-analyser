"""Identidades determinísticas de contratos, sem acesso ao runtime."""
import hashlib
import json

def assinatura(valor):
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf8")).hexdigest()
