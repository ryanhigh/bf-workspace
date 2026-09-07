#!/usr/bin/env python3
"""Generate a fresh enode + nodekey for the eclipse / gethlighting
profiles. Uses Dockerised geth to derive a real secp256k1 key, so we
don't need to install a Python secp256k1 lib.
"""
import json
import os
import subprocess
import sys
import tempfile

if len(sys.argv) > 1:
    image = sys.argv[1]
else:
    image = "ethereum/client-go:latest"

work = tempfile.mkdtemp(prefix="erl_keygen_")
keyfile = os.path.join(work, "key")
# `geth account new` would prompt for password; use `geth --password ...`
# but easier: write a small Go-style dump via `bootnode -genkey` is
# preferred. Some geth images ship bootnode. Try that first.
for binname in ("bootnode", "/usr/local/bin/bootnode"):
    rc = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", binname, image,
         "-genkey", keyfile, "-write"],
        capture_output=True, text=True,
    ).returncode
    if rc == 0:
        break
else:
    # fallback: derive via geth devp2p
    rc = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "/bin/sh", image,
         "-c",
         "set -eu\n"
         "if [ ! -f /usr/local/bin/bootnode ]; then\n"
         "  echo 'no bootnode binary'\n"
         "  exit 1\n"
         "fi\n"
         f"bootnode -genkey {keyfile}\n"
         ],
        capture_output=True, text=True,
    ).returncode
    if rc != 0:
        sys.stderr.write("could not generate key\n")
        sys.exit(1)

key_hex = open(keyfile).read().strip()
# derive enode pubkey via bootnode -nodekeyhex
p = subprocess.run(
    ["docker", "run", "--rm", "--entrypoint", "/bin/sh", image,
     "-c",
     f"bootnode -nodekeyhex {key_hex} -writeaddress"],
    capture_output=True, text=True,
)
pub = p.stdout.strip().splitlines()[-1].strip()
print(json.dumps({
    "nodekey_hex": key_hex,
    "enode_pub_hex": pub,
    "enode_url": f"enode://{pub}@172.80.1.10:30303",
}, indent=2))
# cleanup
subprocess.run(["rm", "-rf", work])