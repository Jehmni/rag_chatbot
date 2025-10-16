import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _fetch_keyvault_secret(vault_url: str, secret_name: str) -> Optional[str]:
    """Attempt to fetch a secret from Azure Key Vault using DefaultAzureCredential.

    This is optional and will silently return None if the azure packages are not
    installed or credentials are not available. Keep Key Vault usage behind an
    env var (`AZURE_KEY_VAULT_URL`) so it's explicit in production.
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except Exception:
        # azure packages not installed or import failed
        return None

    try:
        cred = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=cred)
        secret = client.get_secret(secret_name)
        return secret.value
    except Exception:
        return None


def load_clients(clients_path: Path) -> Dict[str, Any]:
    """Load clients.json and resolve env var references and Key Vault placeholders.

    Supported patterns in `clients.json`:
    - `openai_api_key_env`: name of an environment variable containing the key
    - `search_api_key_env`: name of an environment variable
    - If the env var value itself starts with `keyvault:secret-name`, and
      `AZURE_KEY_VAULT_URL` is set, the loader will attempt to fetch that secret
      from Key Vault. If Key Vault is unavailable the fallback is the env var value.
    """
    try:
        with open(clients_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}

    vault_url = os.getenv("AZURE_KEY_VAULT_URL")
    resolved: Dict[str, Any] = {}
    for cid, cfg in raw.items():
        resolved_cfg = dict(cfg)
        # common pattern: <something>_api_key_env -> env var name
        for key in list(cfg.keys()):
            if key.endswith("_api_key_env"):
                env_name = cfg.get(key)
                if not env_name:
                    continue
                # env_name may itself be a keyvault pointer like "keyvault:secret-name"
                if isinstance(env_name, str) and env_name.startswith("keyvault:"):
                    secret_name = env_name.split("keyvault:", 1)[1]
                    value = None
                    if vault_url:
                        value = _fetch_keyvault_secret(vault_url, secret_name)
                    # fallback to looking up a regular env var with the same name
                    if value is None:
                        value = os.getenv(env_name)
                    secret_key = key.replace("_env", "")
                    resolved_cfg[secret_key] = value
                else:
                    # normal env var lookup
                    secret_key = key.replace("_env", "")
                    resolved_cfg[secret_key] = os.getenv(env_name)

        resolved[cid] = resolved_cfg

    return resolved
