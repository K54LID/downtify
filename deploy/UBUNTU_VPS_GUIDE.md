# Ubuntu 22.04 / 24.04 VPS deployment

## 1. Server prep

```bash
sudo apt update && sudo apt -y upgrade
sudo apt install -y git ffmpeg python3.12 python3.12-venv build-essential \
    postgresql redis-server nginx
sudo systemctl enable --now postgresql redis-server nginx
```

## 2. Create user + database

```bash
sudo adduser --disabled-password --gecos "" Downtify
sudo -u postgres psql -c "CREATE USER Downtify WITH PASSWORD 'changeme';"
sudo -u postgres psql -c "CREATE DATABASE Downtify OWNER Downtify;"
```

## 3. Clone & install

```bash
sudo -iu Downtify
git clone <YOUR_REPO_URL> /opt/Downtify-bot
cd /opt/Downtify-bot
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # fill BOT_TOKEN, ADMIN_IDS, POSTGRES_*, REDIS_HOST=localhost
alembic upgrade head
exit
```

Adjust `.env`:

```
POSTGRES_HOST=localhost
REDIS_HOST=localhost
```

## 4. systemd

```bash
sudo cp /opt/Downtify-bot/deploy/Downtify-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now Downtify-bot
sudo journalctl -u Downtify-bot -f
```

## 5. (Optional) Webhook mode + HTTPS

If you want webhook mode instead of long polling:
- Set `WEBHOOK_URL=https://yourdomain.com` and `WEBHOOK_SECRET=<random>` in `.env`
- Point your domain at the server
- Issue TLS certs:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

- Add proxy rule in `/etc/nginx/sites-available/Downtify.conf`:

```
server {
    listen 443 ssl;
    server_name yourdomain.com;
    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    client_max_body_size 60M;

    location /webhook {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/Downtify.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl restart Downtify-bot
```

## 6. Docker alternative

```bash
git clone <YOUR_REPO_URL> Downtify-bot && cd Downtify-bot
cp .env.example .env && nano .env
docker compose up -d --build
docker compose exec bot alembic upgrade head
docker compose logs -f bot
```

## 7. Telegram Stars setup

In @BotFather:
- enable payments is NOT required for Stars (XTR currency)
- set bot description, about text, commands list

After deploy, set commands via the bot itself (auto on startup) or in @BotFather.

## 8. Upgrades

```bash
cd /opt/Downtify-bot
sudo -u Downtify git pull
sudo -u Downtify /opt/Downtify-bot/.venv/bin/pip install -r requirements.txt
sudo -u Downtify /opt/Downtify-bot/.venv/bin/alembic upgrade head
sudo systemctl restart Downtify-bot
```
