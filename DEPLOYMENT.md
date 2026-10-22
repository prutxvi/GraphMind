# Deployment Guide

This guide covers deploying GraphMind to production environments.

## 🚀 Prerequisites

- Server with Python 3.9+ and Node.js 18+
- Domain name (optional but recommended)
- SSL certificate (for HTTPS)
- Sarvam API key (or any OpenAI-compatible endpoint)

## 📦 Backend Deployment

### Option 1: Traditional Server (Linux/Ubuntu)

#### 1. Setup Server
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx -y
```

#### 2. Clone Repository
```bash
cd /var/www
sudo git clone https://github.com/prutxvi/GraphMind.git
cd GraphMind/backend
sudo chown -R $USER:$USER .
```

#### 3. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 4. Configure Environment
```bash
cp .env.example .env
nano .env
# Add your SARVAM_API_KEY
```

#### 5. Create Systemd Service
```bash
sudo nano /etc/systemd/system/graphmind-backend.service
```

Add:
```ini
[Unit]
Description=GraphMind Backend Service
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/var/www/GraphMind/backend
Environment="PATH=/var/www/GraphMind/backend/venv/bin"
ExecStart=/var/www/GraphMind/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 6. Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable graphmind-backend
sudo systemctl start graphmind-backend
sudo systemctl status graphmind-backend
```

### Option 2: Docker

#### Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app/backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Build & Run
```bash
docker build -t graphmind-backend .
docker run -d \
  -p 8000:8000 \
  -e SARVAM_API_KEY=your_key \
  --name graphmind-backend \
  graphmind-backend
```

## 🎨 Frontend Deployment

### Option 1: Nginx Static Hosting

#### 1. Build Frontend
```bash
cd /var/www/GraphMind/frontend
npm install
npm run build
```

#### 2. Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/graphmind
```

Add:
```nginx
upstream graphmind_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Static frontend
    root /var/www/GraphMind/frontend/dist;
    index index.html;

    # Frontend routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://graphmind_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (if needed)
    location /ws {
        proxy_pass http://graphmind_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 3. Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/graphmind /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Option 2: Vercel (Recommended for React)

```bash
npm install -g vercel
cd frontend
vercel --prod
```

Follow prompts and set environment variables for backend URL.

## 🔒 Security Checklist

- [ ] HTTPS enabled with valid SSL certificate
- [ ] CORS properly configured (not `*` in production)
- [ ] API keys stored in secure `.env` files
- [ ] Database backups configured (if using database)
- [ ] Firewall rules properly set
- [ ] Rate limiting enabled on API endpoints
- [ ] Logging and monitoring configured
- [ ] Regular security updates applied

### Update CORS in main.py:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # Specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📊 Monitoring & Logging

### Backend Logs
```bash
sudo journalctl -u graphmind-backend -f
```

### Nginx Logs
```bash
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Setup Application Monitoring
```python
# Add to main.py for better error tracking
from sentry_sdk import init as sentry_init

sentry_init("your-sentry-dsn")
```

## 🔄 Updates & Maintenance

### Update Application
```bash
cd /var/www/GraphMind
git pull origin main

cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart graphmind-backend

cd ../frontend
npm install
npm run build
```

### Database Backups
```bash
# If using database, setup automatic backups
0 2 * * * /usr/local/bin/backup-graphmind.sh
```

## 🆘 Troubleshooting

### Service Won't Start
```bash
# Check logs
sudo journalctl -u graphmind-backend -n 50
# Verify virtual environment
source /var/www/GraphMind/backend/venv/bin/activate
python -c "import fastapi; print('OK')"
```

### CORS Errors
- Verify frontend URL matches CORS_ORIGINS in backend
- Check browser console for exact error message

### 502 Bad Gateway
- Verify backend is running: `systemctl status graphmind-backend`
- Check Nginx upstream configuration
- Review Nginx error logs

## 📞 Support

For deployment issues:
1. Check logs first
2. Review troubleshooting section
3. Open an issue on GitHub with logs
4. Include server specs and error messages

---

**Happy Deploying! 🚀**
