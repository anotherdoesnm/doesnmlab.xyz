# The mail relay as a container: Debian postfix with the SASL pieces it needs.
# The configuration is our own (mounted), so the image only has to provide a
# working postfix + saslauthd.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && echo "postfix postfix/main_mailer_type select No configuration" | debconf-set-selections \
 && apt-get install -y --no-install-recommends \
      postfix postfix-cdb postfix-lmdb libsasl2-modules sasl2-bin ca-certificates tzdata procps \
 && rm -rf /var/lib/apt/lists/*

# Configuration is baked in, not mounted over /etc/postfix: a bind mount would hide
# the image's dynamicmaps.cf, and Debian ships cdb/hash/ldap support as separate
# plugins that are registered through exactly that file.
COPY postfix/main.cf postfix/master.cf postfix/transport postfix/aliases /etc/postfix/

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
