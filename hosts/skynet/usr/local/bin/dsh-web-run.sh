#!/bin/bash
INC=/etc/nginx/dsh_token.inc
stdbuf -oL -eL /bin/dsh --profile web --no-open --host 127.0.0.1 --port 3080 --trusted-host skynet.doesnmlab.xyz --trusted-host 192.168.1.30 --trusted-host 192.168.1.30:8443 --trusted-host 192.168.1.30:3080 2>&1 | while IFS= read -r line; do
  printf '%s\n' "$line"
  case "$line" in
    *"token="*)
      TOKEN="${line##*token=}"
      TOKEN="${TOKEN%%[[:space:]]*}"
      printf 'set $dsh_launch_token "%s";\n' "$TOKEN" > "$INC"
      nginx -s reload >/dev/null 2>&1 || true
      ;;
  esac
done
