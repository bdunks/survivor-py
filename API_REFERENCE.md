# Quick API Reference

## Start Web Interface
```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

## Key Endpoints

- **Web UI**: http://127.0.0.1:8000/
- **API Docs**: http://127.0.0.1:8000/docs
- **Configuration**: GET/POST `/api/config`
- **Optimization**: GET `/api/optimize/{split_week}`
- **Teams**: GET `/api/teams`
- **CSV Export**: GET `/api/export/csv`

## Quick Test
```bash
curl http://127.0.0.1:8000/api/config
curl http://127.0.0.1:8000/api/teams
curl "http://127.0.0.1:8000/api/optimize/10?year=2024"
```

For full documentation see: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)