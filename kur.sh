#!/bin/bash
# Dolap A1 kurulumu — sunucuda sudo ile çalışır. Dosyalar önce ~/dolap'a kopyalanmış olmalı.
set -euo pipefail
ALAN="SUNUCU-IP.sslip.io"
DIZIN=/home/ubuntu/dolap

echo "### Caddy"
if ! command -v caddy >/dev/null; then
  apt-get install -y -q debian-keyring debian-archive-keyring apt-transport-https curl gnupg >/dev/null
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q >/dev/null
  apt-get install -y -q caddy >/dev/null
fi
caddy version

cat > /etc/caddy/Caddyfile <<EOF
$ALAN {
	encode zstd gzip
	reverse_proxy 127.0.0.1:8090
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options nosniff
		Referrer-Policy no-referrer
		-Server
	}
}
EOF

echo "### Python ortamı"
sudo -u ubuntu bash -c "cd $DIZIN && [ -d venv ] || python3 -m venv venv; venv/bin/pip install -q --upgrade pip; venv/bin/pip install -q -r requirements.txt; venv/bin/python ikon_uret.py"

echo "### Servis"
cp $DIZIN/dolap-api.service /etc/systemd/system/dolap-api.service
systemctl daemon-reload
systemctl enable --now dolap-api
systemctl restart dolap-api
systemctl reload caddy || systemctl restart caddy
sleep 3
systemctl is-active dolap-api caddy
echo KURULUM-TAMAM
