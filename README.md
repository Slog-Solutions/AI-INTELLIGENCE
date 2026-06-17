# ATIP (Army Training Intelligence Platform)

## Overview
ATIP is an offline-first Defence Training Intelligence and Decision Support Platform designed for secure military use. It supports document upload, analytics, semantic search, RAG chat, dashboards, and local LLM integration.

## Tech Stack
- Frontend: React, Vite, TypeScript, TailwindCSS, Recharts, React Query, Zustand
- Backend: FastAPI, Python 3.11+
- Database: PostgreSQL
- Vector store: ChromaDB
- Local LLM: Ollama (default Qwen3 8B), Llama 3 support
- Auth: JWT

## Structure
- `backend/` - FastAPI backend and services
- `frontend/` - React UI application
- `database/` - SQL schema and database utilities
- `uploads/` - Uploaded files storage
- `vector_store/` - ChromaDB embeddings store data
- `models/` - shared models and schemas
- `infra/` - deployment support
- `docs/` - documentation and guides
- `scripts/` - helper scripts
- `samples/` - sample dataset placeholders
- `tests/` - backend and frontend tests

## Quick Start
1. Install PostgreSQL locally.
2. Start PostgreSQL and create database `atip`.
3. Install backend dependencies: `pip install -r backend/requirements.txt`.
4. Start FastAPI: `uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000`.
5. Install frontend dependencies: `npm install` inside `frontend/`.
6. Start UI: `npm run dev`.

## Offline Deployment
See `docs/OFFLINE_DEPLOYMENT.md`.
