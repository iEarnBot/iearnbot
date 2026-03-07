"""
key_store.py — Secure API Key Storage
macOS: uses keychain via subprocess (security command)
Other: AES-256-GCM encrypted file at data/keys.enc
Keys never leave the local machine.
"""

from __future__ import annotations

import os
import sys
import json
import base64
import platform
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
IS_MACOS = platform.system() == "Darwin"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE_DIR = Path(__file__).parent.parent
DATA_DIR = WORKSPACE_DIR / "data"
ENC_FILE = DATA_DIR / "keys.enc"
MASTER_KEY_FILE = Path.home() / ".iearnbot_master.key"

# ---------------------------------------------------------------------------
# macOS Keychain helpers
# ---------------------------------------------------------------------------

def _service_name(market: str, key_name: str) -> str:
    return f"iearnbot/{market}/{key_name}"


def _keychain_set(market: str, key_name: str, value: str) -> bool:
    """Store value in macOS Keychain. Returns True on success."""
    svc = _service_name(market, key_name)
    try:
        result = subprocess.run(
            ["security", "add-generic-password",
             "-a", "iearnbot",
             "-s", svc,
             "-w", value,
             "-U"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Keychain set failed: {e}")
        return False


def _keychain_get(market: str, key_name: str) -> str | None:
    """Retrieve value from macOS Keychain. Returns None if not found."""
    svc = _service_name(market, key_name)
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-a", "iearnbot",
             "-s", svc,
             "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception as e:
        logger.warning(f"Keychain get failed: {e}")
        return None


def _keychain_delete(market: str, key_name: str) -> bool:
    """Delete entry from macOS Keychain. Returns True on success."""
    svc = _service_name(market, key_name)
    try:
        result = subprocess.run(
            ["security", "delete-generic-password",
             "-a", "iearnbot",
             "-s", svc],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Keychain delete failed: {e}")
        return False


def _keychain_list() -> list[dict]:
    """List all iearnbot keychain entries (metadata only)."""
    try:
        result = subprocess.run(
            ["security", "dump-keychain"],
            capture_output=True,
            text=True,
        )
        entries = []
        current_svc = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if '"svce"' in line and '"iearnbot/' in line:
                # Extract service name from: "svce"<blob>="iearnbot/market/key"
                start = line.find('"iearnbot/')
                if start != -1:
                    end = line.find('"', start + 1)
                    if end != -1:
                        current_svc = line[start + 1:end]
            if current_svc:
                parts = current_svc.split("/")
                if len(parts) == 3:
                    entries.append({
                        "market": parts[1],
                        "key_name": parts[2],
                        "backend": "keychain",
                    })
                    current_svc = None
        return entries
    except Exception as e:
        logger.warning(f"Keychain list failed: {e}")
        return []


# ---------------------------------------------------------------------------
# AES-256-GCM encrypted file fallback
# ---------------------------------------------------------------------------

def _get_master_key() -> bytes:
    """
    Load or generate the 32-byte master encryption key.
    Priority: IEARNBOT_MASTER_KEY env var → ~/.iearnbot_master.key file
    """
    env_key = os.environ.get("IEARNBOT_MASTER_KEY")
    if env_key:
        raw = env_key.encode()
        # Pad/truncate to 32 bytes
        return (raw * 2)[:32]

    if MASTER_KEY_FILE.exists():
        return MASTER_KEY_FILE.read_bytes()[:32]

    # Generate new random key
    key = os.urandom(32)
    MASTER_KEY_FILE.write_bytes(key)
    MASTER_KEY_FILE.chmod(0o600)
    logger.info(f"Generated new master key at {MASTER_KEY_FILE}")
    return key


def _enc_load() -> dict:
    """Load and decrypt the encrypted key store. Returns empty dict on failure."""
    if not ENC_FILE.exists():
        return {}
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        master_key = _get_master_key()
        blob = json.loads(ENC_FILE.read_text())
        nonce = base64.b64decode(blob["nonce"])
        ciphertext = base64.b64decode(blob["data"])
        aesgcm = AESGCM(master_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())
    except Exception as e:
        logger.warning(f"Encrypted store load failed: {e}")
        return {}


def _enc_save(store: dict) -> bool:
    """Encrypt and persist the key store. Returns True on success."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        master_key = _get_master_key()
        nonce = os.urandom(12)
        aesgcm = AESGCM(master_key)
        plaintext = json.dumps(store).encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        blob = {
            "nonce": base64.b64encode(nonce).decode(),
            "data": base64.b64encode(ciphertext).decode(),
        }
        ENC_FILE.write_text(json.dumps(blob))
        ENC_FILE.chmod(0o600)
        return True
    except Exception as e:
        logger.warning(f"Encrypted store save failed: {e}")
        return False


def _enc_set(market: str, key_name: str, value: str) -> bool:
    store = _enc_load()
    store[f"{market}/{key_name}"] = value
    return _enc_save(store)


def _enc_get(market: str, key_name: str) -> str | None:
    store = _enc_load()
    return store.get(f"{market}/{key_name}")


def _enc_delete(market: str, key_name: str) -> bool:
    store = _enc_load()
    key = f"{market}/{key_name}"
    if key not in store:
        return False
    del store[key]
    return _enc_save(store)


def _enc_list() -> list[dict]:
    store = _enc_load()
    entries = []
    for k in store:
        parts = k.split("/", 1)
        if len(parts) == 2:
            entries.append({
                "market": parts[0],
                "key_name": parts[1],
                "backend": "encrypted_file",
            })
    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_key(market: str, key_name: str, value: str) -> bool:
    """Store a secret. market = 'polymarket', key_name = 'api_key' / 'private_key'"""
    if IS_MACOS:
        success = _keychain_set(market, key_name, value)
        if success:
            return True
        logger.warning("Keychain set failed, falling back to encrypted file.")
    return _enc_set(market, key_name, value)


def get_key(market: str, key_name: str) -> str | None:
    """Retrieve a secret. Returns None if not found."""
    if IS_MACOS:
        val = _keychain_get(market, key_name)
        if val is not None:
            return val
        # Fall through to encrypted file (key may have been stored there)
    return _enc_get(market, key_name)


def delete_key(market: str, key_name: str) -> bool:
    """Delete a stored secret."""
    deleted = False
    if IS_MACOS:
        deleted = _keychain_delete(market, key_name) or deleted
    deleted = _enc_delete(market, key_name) or deleted
    return deleted


def list_keys() -> list[dict]:
    """List all stored key metadata (names only, not values)."""
    entries = []
    seen = set()

    if IS_MACOS:
        for e in _keychain_list():
            key = (e["market"], e["key_name"])
            if key not in seen:
                seen.add(key)
                entries.append(e)

    for e in _enc_list():
        key = (e["market"], e["key_name"])
        if key not in seen:
            seen.add(key)
            entries.append(e)

    return entries


def test_key(market: str, key_name: str) -> bool:
    """Verify a key exists and is non-empty."""
    val = get_key(market, key_name)
    return bool(val)


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def _cli():
    args = sys.argv[1:]
    if not args:
        print("Usage: key_store.py <set|get|delete|list> [market] [key_name] [value]")
        sys.exit(1)

    cmd = args[0]

    if cmd == "set":
        if len(args) < 4:
            print("Usage: key_store.py set <market> <key_name> <value>")
            sys.exit(1)
        market, key_name, value = args[1], args[2], args[3]
        ok = set_key(market, key_name, value)
        print(f"{'OK' if ok else 'FAILED'}: set {market}/{key_name}")
        sys.exit(0 if ok else 1)

    elif cmd == "get":
        if len(args) < 3:
            print("Usage: key_store.py get <market> <key_name>")
            sys.exit(1)
        market, key_name = args[1], args[2]
        val = get_key(market, key_name)
        if val is None:
            print(f"NOT FOUND: {market}/{key_name}")
            sys.exit(1)
        print(val)

    elif cmd == "delete":
        if len(args) < 3:
            print("Usage: key_store.py delete <market> <key_name>")
            sys.exit(1)
        market, key_name = args[1], args[2]
        ok = delete_key(market, key_name)
        print(f"{'OK' if ok else 'NOT FOUND'}: delete {market}/{key_name}")
        sys.exit(0 if ok else 1)

    elif cmd == "list":
        keys = list_keys()
        if not keys:
            print("No keys stored.")
        else:
            for entry in keys:
                print(f"  {entry['market']}/{entry['key_name']}  [{entry['backend']}]")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    _cli()
