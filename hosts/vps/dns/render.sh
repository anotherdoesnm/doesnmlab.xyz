#!/bin/sh
# Render knot.conf from the template. The TSIG secret is the only thing that is not
# in git: it lives in ./tsig-acme on the host (and in the password manager).
set -eu
cd "$(dirname "$0")"
[ -r tsig-acme ] || { echo "tsig-acme missing: put the ACME TSIG secret there first" >&2; exit 1; }
sed "s|__TSIG_SECRET__|$(cat tsig-acme)|" knot/knot.conf.template > knot/knot.conf
chmod 600 knot/knot.conf
echo "rendered knot/knot.conf"
