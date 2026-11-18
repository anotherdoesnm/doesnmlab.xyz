#!/usr/bin/env bash
# Sunshine game stream host (CT152). Run inside the container, as root.
#
# The container itself is not created here: it needs privileges and device access that
# `pct create` takes on the host. See README.md for the exact command line.
set -euo pipefail

SUNSHINE_VERSION="2026.914.233613"
SUNSHINE_DEB="sunshine_${SUNSHINE_VERSION}-1+debiantrixie_amd64.deb"
SUNSHINE_URL="https://github.com/SunshineStream/Sunshine/releases/download/v${SUNSHINE_VERSION}/${SUNSHINE_DEB}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

# Debian 13 only: the package wants libc6 >= 2.38 and the t64 package names. On bookworm
# the install fails on dependencies, so the container has to come from the trixie template.
apt-get install -y -qq curl ca-certificates xvfb x11-utils xinput joystick evtest

if [ ! -f "/tmp/${SUNSHINE_DEB}" ]; then
    curl -fsSL -o "/tmp/${SUNSHINE_DEB}" "${SUNSHINE_URL}"
fi
apt-get install -y "/tmp/${SUNSHINE_DEB}"

mkdir -p /root/.config/sunshine
cp etc/sunshine/sunshine.conf /root/.config/sunshine/sunshine.conf

cp etc/systemd/system/xvfb.service /etc/systemd/system/
cp etc/systemd/system/sunshine.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now xvfb sunshine

echo "Sunshine is up: https://<container-ip>:47990"
echo "Set the web password once with: sunshine --creds <user> <password>"
