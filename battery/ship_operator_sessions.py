"""Optional shared-service identities with independent durable operator ledgers.

SHIP_MANIFEST:
META:
  name: operator_sessions
  author: robin
  kind: type
  capabilities: [ANALYZE]
  domains: [armada-battery]
  description: Signed operator sessions and isolated evidence ledger routing
"""
from __future__ import annotations
import base64
from contextvars import ContextVar
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import threading
import time

identity = ContextVar('battery_identity', default=None)
_engines = {}
_lock = threading.Lock()


def configured():
    return bool(os.getenv('BATTERY_OPERATORS_FILE'))


def registry():
    path = Path(os.environ['BATTERY_OPERATORS_FILE'])
    if path.stat().st_size > 32768:
        raise ValueError('Operator registry exceeds size limit')
    entries = json.loads(path.read_text())
    if not isinstance(entries, dict) or not 1 <= len(entries) <= 32:
        raise ValueError('Operator registry must contain 1 to 32 identities')
    if len(os.getenv('BATTERY_SESSION_KEY', '')) < 32:
        raise ValueError('Shared sessions require a signing key of at least 32 characters')
    hashes = set()
    for name, row in entries.items():
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', name) or not isinstance(row, dict):
            raise ValueError('Invalid operator identity')
        if set(row) != {'key_sha256', 'role'} or not isinstance(row['role'], str) or row['role'] not in {'operator', 'observer'}:
            raise ValueError('Invalid operator role or credential fields')
        digest = row['key_sha256']
        if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest) or digest in hashes:
            raise ValueError('Operator credential hashes must be valid and unique')
        hashes.add(digest)
    return entries


def sign(payload):
    return hmac.new(os.environ['BATTERY_SESSION_KEY'].encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue(key):
    if not 32 <= len(key) <= 512:
        return None
    digest = hashlib.sha256(key.encode()).hexdigest()
    for name, row in registry().items():
        if hmac.compare_digest(digest, row['key_sha256']):
            payload = base64.urlsafe_b64encode(json.dumps({'sub': name, 'exp': int(time.time()) + 3600, 'version': digest, 'role': row['role']}, separators=(',', ':')).encode()).decode()
            return name, payload + '.' + sign(payload)
    return None


def resolve(token):
    entries = registry()  # Reload permits credential/role revocation on next request.
    try:
        if len(token) > 2048:
            return None
        payload, signature = token.split('.', 1)
        if not hmac.compare_digest(signature, sign(payload)):
            return None
        claim = json.loads(base64.urlsafe_b64decode(payload))
        row = entries.get(claim['sub'])
        if row and claim['exp'] > time.time() and claim['version'] == row['key_sha256'] and claim['role'] == row['role']:
            return {'name': claim['sub'], 'role': row['role']}
    except (ValueError, KeyError, TypeError):
        pass
    return None


def operator_engine(name, factory):
    # Name is validated by the registry before any filesystem operation.
    if name not in registry():
        raise KeyError('Operator unavailable')
    root = Path(os.getenv('BATTERY_OPERATOR_LEDGER_ROOT', 'var/operators')).resolve()
    key = (str(root), name)
    with _lock:
        if key not in _engines:
            path = root / hashlib.sha256(name.encode()).hexdigest() / 'ledger.jsonl'
            _engines[key] = factory(ledger_path=path)
        return _engines[key]
