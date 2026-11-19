#!/usr/bin/env python3
"""Minimal IRC client: SASL PLAIN login, join channels, invite the bridge bot."""
import base64, socket, sys, time

HOST, PORT = "172.18.0.2", 6667
NICK = sys.argv[1]
TOKEN = sys.argv[2]
CHANNELS = sys.argv[3].split(",")
INVITE = sys.argv[4] if len(sys.argv) > 4 else ""

sock = socket.create_connection((HOST, PORT), timeout=10)
buf = b""


def send(line):
    sock.sendall((line + "\r\n").encode())
    print(">>", line if not line.startswith("AUTHENTICATE") else "AUTHENTICATE ***")


def read_until(predicate, timeout=12):
    global buf
    end = time.time() + timeout
    while time.time() < end:
        while b"\r\n" in buf:
            line, buf = buf.split(b"\r\n", 1)
            text = line.decode("utf-8", "replace")
            print("<<", text[:160])
            if predicate(text):
                return text
        sock.settimeout(max(0.2, end - time.time()))
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            raise SystemExit("соединение закрыто")
        buf += chunk
    return ""


send("CAP LS 302")
read_until(lambda t: " CAP " in t and " LS " in t)
send(f"NICK {NICK}")
send(f"USER {NICK} 0 * :{NICK}")
send("AUTHENTICATE PLAIN")
read_until(lambda t: "AUTHENTICATE +" in t)
payload = base64.b64encode(f"\0{NICK}\0{TOKEN}".encode()).decode()
send(f"AUTHENTICATE {payload}")
res = read_until(lambda t: " 900 " in t or " 903 " in t or " 904 " in t or " 905 " in t)
if " 904 " in res or " 905 " in res:
    raise SystemExit("SASL отклонён")
send("CAP END")
read_until(lambda t: " 001 " in t)
for ch in CHANNELS:
    send(f"JOIN {ch}")
    read_until(lambda t: " JOIN " in t or " 403 " in t or " 475 " in t, timeout=6)
if INVITE:
    for ch in CHANNELS:
        send(f"INVITE {INVITE} {ch}")
        time.sleep(1)
time.sleep(1)
send("QUIT :done")
