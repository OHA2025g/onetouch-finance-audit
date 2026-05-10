"""Resolve connector credentials from env or vault references (no secrets in Mongo)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from app.connectors.types import ConnectorCredentialRef


def _parse_secret_blob(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        return json.loads(raw)
    # key=value lines
    out: Dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def fetch_vault_secret(*, vault_provider: str, vault_secret_id: str, rotation_version: Optional[str]) -> Dict[str, Any]:
    """Load a JSON secret object. Production: wire AWS SM / Vault / Azure; dev: env_bridge."""
    if not vault_secret_id:
        raise ValueError("vault_secret_id is required for vault_ref")

    vp = (vault_provider or "env_bridge").lower()
    if vp == "env_bridge":
        # Dev / CI: secret JSON in env — key is the vault_secret_id (e.g. SAP_ODATA_CREDS_JSON)
        raw = os.environ.get(vault_secret_id)
        if not raw:
            raise OSError(f"env_bridge: missing environment variable {vault_secret_id}")
        return _parse_secret_blob(raw)

    if vp == "aws_secretsmanager":
        try:
            import boto3  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("boto3 required for aws_secretsmanager") from e
        client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"))
        kwargs: Dict[str, Any] = {"SecretId": vault_secret_id}
        if rotation_version:
            kwargs["VersionStage"] = rotation_version
        resp = client.get_secret_value(**kwargs)
        blob = resp.get("SecretString") or ""
        return _parse_secret_blob(blob)

    if vp == "hashicorp_vault":
        # Optional: HTTP to Vault KV v2 — requires VAULT_ADDR + VAULT_TOKEN in env
        addr = os.environ.get("VAULT_ADDR", "").rstrip("/")
        token = os.environ.get("VAULT_TOKEN", "")
        if not addr or not token:
            raise OSError("hashicorp_vault: set VAULT_ADDR and VAULT_TOKEN")
        import httpx

        path = vault_secret_id.lstrip("/")
        url = f"{addr}/v1/{path}"
        with httpx.Client(timeout=30.0) as c:
            r = c.get(url, headers={"X-Vault-Token": token})
            r.raise_for_status()
        data = r.json().get("data") or {}
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        return dict(inner) if isinstance(inner, dict) else _parse_secret_blob(str(inner))

    if vp == "azure_keyvault":
        # Prefer managed identity + DefaultAzureCredential in production
        vault_name = os.environ.get("AZURE_KEY_VAULT_NAME")
        if not vault_name:
            raise OSError("azure_keyvault: set AZURE_KEY_VAULT_NAME")
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.secrets import SecretClient  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("azure-identity and azure-keyvault-secrets required for azure_keyvault") from e
        uri = f"https://{vault_name}.vault.azure.net/"
        cred = DefaultAzureCredential()
        client = SecretClient(vault_url=uri, credential=cred)
        ver = rotation_version or None
        sec = client.get_secret(vault_secret_id, version=ver)
        return _parse_secret_blob(sec.value or "{}")

    raise ValueError(f"Unsupported vault_provider: {vp}")


def load_connector_credentials(ref: ConnectorCredentialRef) -> Dict[str, Any]:
    """Return a dict with keys like client_id, client_secret, tenant (provider-specific)."""
    if ref.kind == "none":
        return {}
    if ref.kind == "env_ref":
        if not ref.env_key:
            return {}
        raw = os.environ.get(ref.env_key)
        if not raw:
            return {}
        return _parse_secret_blob(raw)
    if ref.kind == "vault_ref":
        vp = str(ref.vault_provider or "env_bridge")
        return fetch_vault_secret(
            vault_provider=vp,
            vault_secret_id=ref.vault_secret_id or "",
            rotation_version=ref.rotation_version,
        )
    return {}
