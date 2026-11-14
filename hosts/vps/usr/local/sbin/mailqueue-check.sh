#!/bin/bash
# Warn when mail for doesnmlab.xyz has been sitting in the relay queue too long.
#
# The queue is the store-and-forward buffer: it is *supposed* to be non-empty
# overnight while nexus is off. So the alarm is deliberately slow -- a full day
# or a hundred messages means the tunnel or the home side has been down longer
# than a normal night, not that mail is flowing.
#
# Uses `postqueue -j`: the textual listing prints arrival times without a year
# ("Fri Nov 13 12:50:52"), which is impossible to age reliably.
set -u

ALERT_TO=""
[ -r /etc/mailqueue-alert.conf ] && . /etc/mailqueue-alert.conf

max_age_hours=${MAX_AGE_HOURS:-24}
max_count=${MAX_COUNT:-100}

queue_json=$(postqueue -j 2>/dev/null)

read -r count age_hours <<<"$(printf '%s\n' "$queue_json" | python3 -c '
import json, sys, time
count = 0
oldest = None
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        entry = json.loads(line)
    except ValueError:
        continue
    count += 1
    at = entry.get("arrival_time")
    if isinstance(at, (int, float)):
        age = time.time() - at
        oldest = age if oldest is None else max(oldest, age)
sys.stdout.write(f"{count} {int(oldest // 3600) if oldest else 0}\n")
' 2>/dev/null)"

count=${count:-0}
age_hours=${age_hours:-0}

reason=""
if [ "$count" -ge "$max_count" ]; then
    reason="в очереди ${count} писем (порог ${max_count})"
fi
if [ "$age_hours" -ge "$max_age_hours" ]; then
    reason="${reason:+$reason; }самое старое ждёт ${age_hours}ч (порог ${max_age_hours}ч)"
fi
[ -z "$reason" ] && exit 0

msg="Релей doesnmlab.xyz: $reason. Проверь туннель на nexus (mail-tunnel) и питание домашней стороны."
logger -t mailqueue "$msg"
[ -n "$ALERT_TO" ] && printf 'Subject: mail queue on relay\nFrom: relay@mail.doesnmlab.xyz\nTo: %s\n\n%s\n' "$ALERT_TO" "$msg" \
    | sendmail -f relay@mail.doesnmlab.xyz "$ALERT_TO"
exit 0
