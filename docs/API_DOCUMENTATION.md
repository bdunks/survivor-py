# NFL Survivor Pool Optimizer - API Documentation

## Overview

The NFL Survivor Pool Optimizer provides a comprehensive REST API built with FastAPI that exposes all functionality for managing configurations, running optimizations, and exporting results.

**Base URL**: `http://127.0.0.1:8000/api`

**Interactive Documentation**: `http://127.0.0.1:8000/docs` (Swagger UI)

## Authentication

No authentication is required for this single-user local instance.

## API Endpoints

### Configuration Management

#### Get Current Configuration
```http
GET /api/config
```

**Response:**
```json
{
  "current_week": 5,
  "user_picks": [
    {
      "team": "SEA",
      "week": 1,
      "spread": 6.0
    }
  ],
  "total_picks": 1
}
```

#### Update Current Week
```http
PUT /api/config/week/{week}
```

**Parameters:**
- `week` (path): Integer between 1-18

**Response:**
```json
{
  "message": "Updated current week to 5",
  "week": 5
}
```

#### Add/Update User Pick
```http
POST /api/config/picks
```

**Request Body:**
```json
{
  "team": "SEA",
  "week": 1,
  "spread": 6.0
}
```

**Response:**
```json
{
  "message": "Added pick for week 1",
  "pick": {
    "team": "SEA",
    "week": 1,
    "spread": 6.0
  }
}
```

#### Clear Specific Week Pick
```http
DELETE /api/config/picks/{week}
```

**Parameters:**
- `week` (path): Integer between 1-18

**Response:**
```json
{
  "message": "Cleared pick for week 1",
  "week": 1
}
```

#### Clear All Picks
```http
DELETE /api/config/picks
```

**Response:**
```json
{
  "message": "Cleared all picks"
}
```

### Data Operations

#### Refresh Odds Data
```http
POST /api/data/refresh?year={year}
```

**Parameters:**
- `year` (query): Integer between 2020-2030

**Response:**
```json
{
  "message": "Refreshed 306 events for 2024",
  "year": 2024,
  "events_count": 306,
  "starting_week": 5
}
```

#### Get Events Data
```http
GET /api/data/events?year={year}
```

**Parameters:**
- `year` (query): Integer between 2020-2030

**Response:**
```json
[
  {
    "event_id": 1234,
    "season_year": 2024,
    "week": 1,
    "short_name": "SEA @ DEN",
    "spread": -6.0,
    "away_team": "SEA",
    "home_team": "DEN",
    "favored_team": "SEA"
  }
]
```

#### Get NFL Teams
```http
GET /api/teams
```

**Response:**
```json
{
  "teams": [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI",
    "CIN", "CLE", "DAL", "DEN", "DET", "GB",
    "HOU", "IND", "JAC", "KC", "LV", "LAC",
    "LAR", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SF", "SEA", "TB",
    "TEN", "WAS"
  ]
}
```

### Optimization Engine

#### Get All Algorithms for Split Week
```http
GET /api/optimize/{split_week}?year={year}
```

**Parameters:**
- `split_week` (path): Integer between 1-18
- `year` (query): Integer between 2020-2030 (optional, defaults to current year)

**Response:**
```json
{
  "split_week": 10,
  "algorithms": {
    "bestSpread": {
      "algorithm": "Best Spread",
      "picks": [
        {
          "team": "DET",
          "week": 2,
          "spread": 7.5
        }
      ],
      "total_spread": 122.0
    },
    "backToFront": {
      "algorithm": "Back to Front",
      "picks": [...],
      "total_spread": 118.5
    },
    "futureValue": {
      "algorithm": "Weighted Future Value",
      "picks": [...],
      "total_spread": 125.0
    }
  }
}
```

#### Get Single Algorithm Result
```http
GET /api/optimize/{split_week}/{algorithm}?year={year}
```

**Parameters:**
- `split_week` (path): Integer between 1-18
- `algorithm` (path): One of `best-spread`, `back-to-front`, `weighted-future-value`
- `year` (query): Integer between 2020-2030 (optional)

**Response:**
```json
{
  "algorithm": "Best Spread",
  "picks": [
    {
      "team": "DET",
      "week": 2,
      "spread": 7.5
    }
  ],
  "total_spread": 122.0
}
```

### Export & Analysis

#### Export to CSV
```http
GET /api/export/csv?split_week={week}&algorithm={algo}&year={year}
```

**Parameters:**
- `split_week` (query): Integer between 1-18
- `algorithm` (query): One of `all`, `best-spread`, `back-to-front`, `weighted-future-value`
- `year` (query): Integer between 2020-2030

**Response:** CSV file download with picks data

#### Get System Status
```http
GET /api/status
```

**Response:**
```json
{
  "current_week": 5,
  "total_picks": 2,
  "database_events": 272,
  "last_refresh": null
}
```

## Error Handling

All endpoints return structured error responses for failures:

```json
{
  "error": "Invalid week: 19. Week must be between 1 and 18.",
  "detail": "Additional error information",
  "status_code": 400
}
```

### Common HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid parameters or request data
- **404 Not Found**: Resource not found (e.g., no data for specified year)
- **422 Unprocessable Entity**: Validation error in request body
- **500 Internal Server Error**: Server-side error

## Data Models

### Pick Object
```json
{
  "team": "string (2-3 characters)",
  "week": "integer (1-18)",
  "spread": "float (optional)"
}
```

### EventOdds Object
```json
{
  "event_id": "integer",
  "season_year": "integer",
  "week": "integer (1-18)",
  "short_name": "string (e.g., 'SEA @ DEN')",
  "spread": "float",
  "away_team": "string",
  "home_team": "string",
  "favored_team": "string"
}
```

### Algorithm Result
```json
{
  "algorithm": "string",
  "picks": "array of Pick objects",
  "total_spread": "float"
}
```

## Usage Examples

### JavaScript/Web Integration

```javascript
// Get current configuration
const config = await fetch('/api/config').then(r => r.json());

// Add a pick
await fetch('/api/config/picks', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    team: 'SEA',
    week: 1,
    spread: 6.0
  })
});

// Get optimization results
const results = await fetch('/api/optimize/10?year=2024')
  .then(r => r.json());

// Export CSV
const csvBlob = await fetch('/api/export/csv?split_week=10&algorithm=all&year=2024')
  .then(r => r.blob());
```

### Python Integration

```python
import requests

base_url = "http://127.0.0.1:8000/api"

# Get configuration
config = requests.get(f"{base_url}/config").json()

# Add a pick
response = requests.post(f"{base_url}/config/picks", json={
    "team": "SEA",
    "week": 1, 
    "spread": 6.0
})

# Get optimization
optimization = requests.get(f"{base_url}/optimize/10?year=2024").json()

# Download CSV
csv_data = requests.get(
    f"{base_url}/export/csv?split_week=10&algorithm=all&year=2024"
).content
```

### cURL Examples

```bash
# Get configuration
curl http://127.0.0.1:8000/api/config

# Add pick
curl -X POST http://127.0.0.1:8000/api/config/picks \
  -H "Content-Type: application/json" \
  -d '{"team": "SEA", "week": 1, "spread": 6.0}'

# Get optimization results
curl "http://127.0.0.1:8000/api/optimize/10?year=2024"

# Download CSV
curl "http://127.0.0.1:8000/api/export/csv?split_week=10&algorithm=all&year=2024" \
  --output picks.csv
```

## Rate Limiting

No rate limiting is implemented for this local single-user application.

## Versioning

The API is currently unversioned. Breaking changes will be documented in release notes.

## OpenAPI Specification

The complete OpenAPI specification is available at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **JSON Schema**: `http://127.0.0.1:8000/openapi.json`

## Support

For API issues or questions:
1. Check the interactive documentation at `/docs`
2. Review error responses for detailed information
3. Consult the main project documentation

## Development Notes

- All endpoints support CORS for local development
- User picks are automatically validated for team codes and week ranges
- Configuration changes are persisted to `config.json` immediately
- Database operations use SQLite with automatic connection management
- CSV exports are generated dynamically and include all user-defined picks