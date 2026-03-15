#!/usr/bin/env bash
# One-time Samba setup for Spark.
# Binds to tailscale0 only. Shares ~/babs-data as \\100.109.213.22\babs-data.
# Run as root: sudo bash scripts/samba-setup.sh

set -euo pipefail

TAILSCALE_IP="100.109.213.22"
SHARE_PATH="/home/dave/babs-data"
SMB_CONF="/etc/samba/smb.conf"

echo "==> Backing up existing smb.conf..."
cp "$SMB_CONF" "${SMB_CONF}.bak.$(date +%Y%m%d%H%M%S)"

echo "==> Writing new smb.conf..."
cat > "$SMB_CONF" << 'EOF'
[global]
   workgroup = WORKGROUP
   server string = Spark
   server role = standalone server

   # Bind only to Tailscale interface - not exposed to LAN
   interfaces = tailscale0
   bind interfaces only = yes

   # Disable printer sharing
   load printers = no
   printing = bsd
   printcap name = /dev/null
   disable spoolss = yes

   # Logging
   log file = /var/log/samba/log.%m
   max log size = 1000
   logging = file
   panic action = /usr/share/samba/panic-action %d

   # Auth
   security = user
   passdb backend = tdbsam
   obey pam restrictions = yes
   unix password sync = no
   pam password change = no
   map to guest = never

[babs-data]
   comment = Babs Data (models, outputs, etc.)
   path = /home/dave/babs-data
   browseable = yes
   read only = no
   valid users = dave
   create mask = 0644
   directory mask = 0755
   force user = dave
EOF

echo "==> Enabling and starting smbd..."
systemctl enable smbd
systemctl restart smbd

echo ""
echo "==> Done. One step left - set the Samba password for dave:"
echo ""
echo "    sudo smbpasswd -a dave"
echo ""
echo "==> Then on Windows, map a network drive to:"
echo "    \\\\100.109.213.22\\babs-data"
echo ""
echo "==> Test with: smbclient //100.109.213.22/babs-data -U dave"
