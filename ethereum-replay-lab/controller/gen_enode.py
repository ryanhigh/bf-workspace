#!/usr/bin/env python3
"""Generate a fresh enode URL for the eclipse / gethlighting profiles.

Strategy: launch a throwaway geth dev instance, query its admin.nodeInfo
for the real enode URL, then kill the container. This is the only
reliable way to get a valid secp256k1 pubkey without a local keygen
library.

The returned `enode_url` is suitable for `--bootnodes=...`.
"""
from __future__ import annotations
import json
import subprocess
import sys
import time

import secrets


def sh(cmd, timeout=60):
    out = subprocess.run(cmd, capture_output=True, text=True,
                         timeout=timeout, check=False)
    return out.returncode, out.stdout, out.stderr


def main():
    image = "ethereum/client-go:latest"
    nodekey = sys.argv[1] if len(sys.argv) > 1 else secrets.token_hex(32)
    name = f"erl-keygen-{secrets.token_hex(4)}"
    rc, _, err = sh([
        "docker", "run", "-d", "--rm",
        "--name", name,
        "--entrypoint", "/bin/sh", image,
        "-c",
        f"geth --dev --nodekeyhex {nodekey} --http --http.addr=0.0.0.0 "
        f"--http.port=8545 --http.api=admin,eth,net,web3 --ipcdisable "
        f"--port=30303 --maxpeers=0",
    ])
    if rc != 0:
        print(f"failed to start geth dev: {err}", file=sys.stderr)
        return 1
    # wait for the http server to come up
    enode_url = None
    for _ in range(30):
        time.sleep(1)
        rc, out, err = sh([
            "docker", "exec", name,
            "wget", "-qO-", "--timeout=3",
            "--header=Content-Type: application/json",
            "--post-data={\"jsonrpc\":\"2.0\",\"method\":\"admin_nodeInfo\","
            "\"params\":[],\"id\":1}",
            "http://127.0.0.1:8545",
        ])
        if rc == 0 and out.strip():
            try:
                obj = json.loads(out)
                enode_url = obj["result"]["enode"]
                break
            except Exception:
                pass
    sh(["docker", "rm", "-f", name])
    if not enode_url:
        print("could not derive enode", file=sys.stderr)
        return 2
    print(json.dumps({
        "nodekey_hex": nodekey,
        "enode_url": enode_url,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())