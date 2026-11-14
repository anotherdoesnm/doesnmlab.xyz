#!/bin/sh
# Everything that has to happen before postfix starts, in order:
#   * render the transport map (cdb, because that is what main.cf asks for);
#   * rebuild the alias database;
#   * bring up saslauthd with the sasldb backend on the socket postfix expects.
set -eu

# The SASL database is mounted read-only from the host; a bind mount keeps the
# host's group id, which the container's postfix user does not share. Copy it in
# with the container's own ownership instead.
if [ -r /secrets/sasldb2 ]; then
    cp /secrets/sasldb2 /etc/sasldb2
    chown root:postfix /etc/sasldb2
    chmod 640 /etc/sasldb2
fi

postmap /etc/postfix/transport
newaliases 2>/dev/null || true

# smtpd runs chrooted, so saslauthd's socket must live inside the chroot; the
# /var/run/saslauthd symlink keeps non-chrooted tools (testsaslauthd) working.
SOCK=/var/spool/postfix/var/run/saslauthd
mkdir -p "$SOCK"
rm -rf /var/run/saslauthd
ln -sfn "$SOCK" /var/run/saslauthd
chown -R root:sasl "$SOCK"
rm -f "$SOCK/mux"
saslauthd -a sasldb -m "$SOCK" -n 2

# The queue and its index files must belong to postfix inside the container.
chown -R postfix:postfix /var/spool/postfix /var/lib/postfix 2>/dev/null || true

exec postfix start-fg
