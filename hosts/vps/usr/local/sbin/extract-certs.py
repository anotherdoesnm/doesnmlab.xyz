#!/usr/bin/env python3
"""Lay out TLS material from Traefik's acme.json as <domain>.crt / .key files.

Contract with /usr/local/bin/nexus-cert-export (the forced command): it tars the
directory /root/tls-out and streams it to nexus, so this script only has to keep
that directory current. The wildcard is written as wildcard.doesnmlab.xyz.* — the
fallback name refresh-certs.sh looks for when a domain has no certificate of its own.

Lives in /usr/local/sbin on purpose: /root is where throwaway scripts pile up, and
`rm *.py` there has already eaten this file once.
"""
import base64
import json
import os

ACME = "/root/certs/acme.json"
OUT = "/root/tls-out"
WILDCARD = "wildcard.doesnmlab.xyz"


def main() -> None:
    data = json.load(open(ACME))
    os.makedirs(OUT, exist_ok=True)
    written = 0
    for _resolver, store in data.items():
        for cert in store.get("Certificates", []):
            domain = cert.get("domain", {}).get("main", "")
            if not domain:
                continue
            name = WILDCARD if domain.startswith("*.") else domain
            crt = base64.b64decode(cert["certificate"]).decode()
            key = base64.b64decode(cert["key"]).decode()
            for suffix, payload in ((".crt", crt), (".key", key)):
                path = os.path.join(OUT, name + suffix)
                with open(path, "w") as fh:
                    fh.write(payload)
                os.chmod(path, 0o600)
            written += 1
    print(f"wrote {written} certificates to {OUT}", flush=True)


if __name__ == "__main__":
    main()
