#!/usr/bin/env python3
"""Join a channel as probe and print what is said for N seconds."""
import base64, os, socket, sys, time
sock = socket.create_connection(("172.18.0.2", 6667), timeout=10)
buf = b""
def send(l): sock.sendall((l + "\r\n").encode())
def pump(sec):
    global buf
    out = []
    end = time.time() + sec
    while time.time() < end:
        sock.settimeout(max(0.2, end - time.time()))
        try: chunk = sock.recv(8192)
        except socket.timeout: break
        if not chunk: break
        buf += chunk
        while b"\r\n" in buf:
            line, buf = buf.split(b"\r\n", 1)
            out.append(line.decode("utf-8", "replace"))
    return out
send("CAP LS 302"); pump(1)
send("NICK probe"); send("USER probe 0 * :probe")
send("AUTHENTICATE PLAIN"); pump(1)
token = os.environ.get("IRC_TOKEN", "")
if not token:
    raise SystemExit("IRC_TOKEN is not set")
send("AUTHENTICATE " + base64.b64encode(f"\0probe\0{token}".encode()).decode()); pump(1)
send("CAP END"); pump(1)
send("JOIN " + sys.argv[1]); pump(2)
for line in pump(int(sys.argv[2])):
    if "PRIVMSG" in line: print(line[:160])
send("QUIT :done")
