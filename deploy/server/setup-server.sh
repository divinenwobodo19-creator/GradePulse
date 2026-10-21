#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu server (run ON the server, with sudo).
# Installs Docker and opens ports 80/443 in the server's own firewall.
# Oracle Cloud images ship iptables rules that block everything except SSH,
# so the cloud "security list" rule alone is not enough.
set -euo pipefail

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
usermod -aG docker "${SUDO_USER:-ubuntu}"

if command -v iptables >/dev/null; then
  for port in 80 443; do
    iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null \
      || iptables -I INPUT 6 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  done
  if command -v netfilter-persistent >/dev/null; then netfilter-persistent save; fi
fi
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp && ufw allow 443/tcp
fi

# A little swap so building the web app never runs out of memory.
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q /swapfile /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

echo "Server ready. Log out and back in once so the docker group applies."
