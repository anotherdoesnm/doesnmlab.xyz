#!/bin/sh
# Refresh the dn42 ROA table for BIRD and reload it.
#
# Silent on success on purpose: this runs every 15 minutes, and cron mails any
# output to root. Printing only when something breaks keeps the mailbox useful.
# BIRD also carries the default route for 212.192.223.99, so a failed reload is
# worth an email, and a successful one is not.
set -u
URL='https://dn42.burble.com/roa/dn42_roa_bird2_6.conf'
FILE='/etc/bird/roa_dn42_v6.conf'

out=$(curl -sfSLR -o "$FILE" -z "$FILE" "$URL" 2>&1) || {
    echo "ROA download failed: ${out:-no output}"
    exit 1
}

out=$(/usr/sbin/birdc configure 2>&1) || {
    echo "birdc configure failed: $out"
    exit 1
}

case "$out" in
    *rror*)
        echo "birdc reported an error: $out"
        exit 1
        ;;
esac

exit 0
