# Changelog

All notable changes to the NFL Survivor Pool Optimizer will be documented in this file.

## [2.0.0] - 2025-09-01

### Added - Web Interface Major Release 🌐

#### New Web Interface
- **Modern Web UI**: Complete responsive web interface using Pico CSS
- **Real-time Optimization**: Live updates as you adjust split weeks and picks
- **Interactive User Picks**: Add/remove picks with dropdown selections
- **Algorithm Comparison**: Side-by-side visualization of all three optimization strategies
- **Color-coded Results**: Visual indicators for algorithm differences and changes
- **CSV Export**: Download optimized picks directly from browser

#### FastAPI Backend
- **REST API**: Complete RESTful API with automatic OpenAPI documentation  
- **Type Safety**: Pydantic models for request/response validation
- **Configuration Management**: API endpoints for all configuration operations
- **Real-time Data**: Live optimization results with user pick integration
- **Error Handling**: Structured error responses with proper HTTP status codes

#### Enhanced Configuration
- **JSON Persistence**: User picks automatically saved to `config.json`
- **CLI Commands**: Added configuration management commands
  - `--status`: View current configuration
  - `--set-week N`: Update current week
  - `--add-pick "TEAM:WEEK:SPREAD"`: Add user pick
  - `--clear-pick N|all`: Clear picks
- **Web-CLI Compatibility**: Configuration shared between web and CLI interfaces

#### API Endpoints
- `GET /api/config` - Current configuration
- `POST /api/config/picks` - Add/update user picks
- `DELETE /api/config/picks/{week}` - Clear picks
- `GET /api/optimize/{split_week}` - All algorithms for split week
- `GET /api/export/csv` - Download CSV results
- `GET /api/teams` - NFL team list
- `POST /api/data/refresh` - Refresh odds data

#### Documentation
- **Comprehensive README**: Updated with web interface instructions
- **API Documentation**: Complete API reference with examples
- **CLAUDE.md Updates**: Development guidance for both interfaces
- **Interactive Docs**: Swagger UI at `/docs` endpoint

### Changed
- **Primary Interface**: Web interface is now the recommended way to use the tool
- **Dependencies**: Added FastAPI, Uvicorn, Pydantic for web functionality
- **File Structure**: Added `app.py`, `api_models.py`, `static/` directory
- **Installation**: UV package manager recommended for dependency management

### Technical Details
- **Framework**: FastAPI with Uvicorn ASGI server
- **Frontend**: Vanilla JavaScript with Pico CSS (no build step required)
- **Validation**: Pydantic models for type-safe API operations
- **Architecture**: RESTful API design with automatic documentation
- **Compatibility**: Existing CLI functionality fully preserved

### Migration Guide
**From CLI to Web Interface:**
1. Install new dependencies: `uv add fastapi uvicorn[standard] pydantic python-multipart`
2. Start web server: `uvicorn app:app --reload --host 127.0.0.1 --port 8000`
3. Open browser to: http://127.0.0.1:8000/
4. Existing picks in `main.py` can be migrated via web interface

**CLI users** can continue using the existing interface without any changes.

---

## [1.0.0] - Previous Release

### Initial Release
- Command-line NFL survivor pool optimizer
- Three optimization algorithms (Best Spread, Back-to-Front, Weighted Future Value)
- CBS Sports data scraping
- SQLite database storage
- Console table visualization with color coding
- CSV export functionality
- User-defined pick support