#!/usr/bin/env python3
"""Create bridge rows in lightning's SQLite database.

bridges/bridge_channels are normally written by `!bridge create` / `!bridge join`,
but those commands require admin rights on both sides — and parley has no operators.
Channel ids carry the plugin instance name: `<plugin>::<channel>`.
"""
import sqlite3, sys, uuid

DB = sys.argv[1]
PAIRS = [("parley::#lobby", "fluxer::1572978870410285056"),
         ("parley::#parley", "fluxer::1572978861983932418"),
         ("parley::#ru", "fluxer::1572978875275681792")]

db = sqlite3.connect(DB)
cur = db.cursor()
for left, right in PAIRS:
    bid = uuid.uuid4().hex
    cur.execute("INSERT INTO bridges (id, codes, allow_everyone, add_platform_name, disable_code_expiry)"
                " VALUES (?, '[]', 0, 0, 1)", (bid,))
    for chan in (left, right):
        cur.execute("INSERT INTO bridge_channels (bridge_id, channel_id, data) VALUES (?, ?, '{}')", (bid, chan))
    print("bridge", left, "<->", right)
db.commit()
db.close()
