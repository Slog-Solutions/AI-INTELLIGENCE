# ATIP Offline Deployment Guide

## Overview
ATIP is designed to run entirely offline with no cloud dependencies. This guide covers deployment on isolated military networks.

## Prerequisites
- PostgreSQL 15+ installed locally
- Python 3.11+ with pip
- Node.js 18+ with npm
- Ollama installed and running locally
- Docker (optional, for containerized deployment)

## Step 1: Database Setup

### Create PostgreSQL Database
```bash
psql -U postgres
CREATE DATABASE atip;
CREATE USER atip_user WITH PASSWORD 'atip_pass';
ALTER ROLE atip_user SET client_encoding TO 'utf8';
ALTER ROLE atip_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE atip_user SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE atip TO atip_user;
\q
```

### Initialize Schema
```bash
cd backend
python scripts/seed_db.py
```

## Step 2: Backend Setup

### Install Python Dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configure Environment
Update `backend/.env`:
```
DATABASE_URL=postgresql+psycopg2://atip_user:atip_pass@localhost:5432/atip
JWT_SECRET_KEY=your-secret-key-here
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3
```

### Start Backend
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Step 3: Frontend Setup

### Install Node Dependencies
```bash
cd frontend
npm install
```

### Build Frontend
```bash
npm run build
```

### Serve Frontend
```bash
npm run dev  # Development
# or
npm run preview  # Production build preview
```

## Step 4: Ollama Local LLM

### Download and Install Ollama
- Download from ollama.ai
- Install for your OS

### Pull Model
```bash
ollama pull qwen3
ollama serve
```

### Verify
```bash
curl http://localhost:11434/api/tags
```

## Step 5: Access ATIP

1. Open browser: `http://localhost:5173`
2. Login with credentials:
   - Username: `admin`
   - Password: `Admin123!`

## Sample Users
- **admin** / Admin123! - Super Admin
- **co_alpha** / CO123! - Commanding Officer
- **instructor_alpha** / Inst123! - Instructor
- **analyst_main** / Ana123! - Analyst

## Docker Deployment

### Build Container
```bash
docker-compose build
```

### Start Services
```bash
docker-compose up -d
```

### Access
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`

## Troubleshooting

### Database Connection
```bash
psql -h localhost -U atip_user -d atip -c "SELECT 1"
```

### Backend Health
```bash
curl http://localhost:8000/
```

### Ollama Status
```bash
ollama list
```

## Security Notes
- Change `JWT_SECRET_KEY` in production
- Use strong PostgreSQL password
- Restrict network access to authorized personnel only
- Disable remote access when on isolated networks
- Keep all systems behind corporate firewall

## Offline Verification Checklist
- [ ] PostgreSQL running locally
- [ ] Backend API accessible
- [ ] Frontend accessible
- [ ] Ollama running with qwen3 model
- [ ] Sample data imported
- [ ] Can login with test user
- [ ] Can upload documents
- [ ] Can perform RAG queries

## Support
For issues, check backend logs:
```bash
tail -f logs/backend.log
```

For frontend errors, check browser console (F12).
