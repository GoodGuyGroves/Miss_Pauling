# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based file server and web interface for managing Team Fortress 2 (TF2) map files. It provides a FastDL (Fast Download) service for game servers and includes a web UI for uploading, managing, and organizing maps into mapcycles.

## Development Setup

### Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Development mode with auto-reload
python main.py

# Production mode via run script
./run.sh

# Direct uvicorn command
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Architecture

### Core Components

- **`main.py`**: FastAPI application entry point with REST API endpoints for map management
- **`core/config.py`**: Pydantic-based configuration management loading from `settings.json`
- **`core/mapcycle.py`**: Manages TF2 server mapcycle files and state persistence
- **`settings.json`**: Configuration file defining servers, paths, and application settings
- **`templates/`**: Jinja2 HTML templates for the web interface
- **`static/`**: CSS and JavaScript assets for the frontend

### Key Features

1. **Map Upload & Management**: RESTful endpoints for uploading .bsp files with size validation
2. **Mapcycle Management**: Toggle maps in/out of server rotation lists across multiple mapcycles
3. **FastDL Server**: Serves map files directly via `/tf/maps/{filename}` endpoints
4. **Multi-Server Support**: Manages mapcycle files for multiple TF2 server instances
5. **Web Interface**: HTML frontend for browsing and managing maps

### Configuration System

The application uses a centralized configuration in `settings.json`:
- `servers`: Array of TF2 server configurations with paths to tf directories
- `maps_dir`: Directory where map files are stored and served from
- `mapcycles`: List of available mapcycle names (e.g., "pt_official", "pt_all")
- File validation settings for allowed extensions and size limits
- CORS and security settings

### Data Persistence

- **`mapcycle.json`**: Persists which maps are enabled in each mapcycle
- **Server mapcycle files**: Generates `mapcycle_{name}.txt` files in each server's cfg directory

## File Structure

```
├── main.py              # FastAPI app with REST endpoints
├── core/
│   ├── config.py        # Settings and validation
│   └── mapcycle.py      # Mapcycle management logic
├── templates/           # Jinja2 HTML templates
├── static/             # Frontend assets (CSS/JS)
├── settings.json       # Application configuration
└── requirements.txt    # Python dependencies
```

## API Endpoints

- `GET /`: Web interface
- `GET /maps`: List all maps with metadata
- `POST /upload`: Upload new map files
- `GET /tf/maps/{filename}`: Serve map files (FastDL)
- `POST /maps/{filename}/mapcycle`: Toggle map in mapcycle
- `DELETE /maps/{filename}`: Delete map and remove from mapcycles

## Development Notes

- Uses async/await patterns throughout with aiofiles for file operations
- Implements proper error handling with HTTP exceptions
- File uploads include size validation and extension checking
- Mapcycle state automatically syncs to server cfg directories
- CORS middleware configured for cross-origin requests
- TrustedHost middleware for security