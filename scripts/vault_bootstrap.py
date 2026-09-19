"""Isolated local Vault bootstrap. Production must use managed unsealing instead."""

import json, os, time
from pathlib import Path
import hvac

state = Path("/vault-bootstrap/local-keys.json")
while True:
    try:
        c = hvac.Client(url=os.environ["VAULT_URL"], timeout=5)
        if not c.sys.is_initialized():
            if state.exists():
                raise RuntimeError("Vault storage missing but bootstrap keys exist")
            keys = c.sys.initialize(secret_shares=1, secret_threshold=1)
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(json.dumps(keys))
            state.chmod(0o600)
        keys = json.loads(state.read_text())
        if c.sys.is_sealed():
            c.sys.submit_unseal_key(keys["keys"][0])
        c.token = keys["root_token"]
        desired = os.environ["VAULT_TOKEN"]
        desired_client = hvac.Client(
            url=os.environ["VAULT_URL"], token=desired, timeout=5
        )
        if not desired_client.is_authenticated():
            c.auth.token.create(id=desired, policies=["root"], no_parent=True)
        if "secret/" not in c.sys.list_mounted_secrets_engines()["data"]:
            c.sys.enable_secrets_engine("kv", path="secret", options={"version": "2"})
    except Exception as exc:
        print("Vault bootstrap waiting: " + type(exc).__name__, flush=True)
    time.sleep(15)
