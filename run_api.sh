#!/bin/bash
# run_api.sh - start the FastAPI backend for testing

# ensure virtualenv is activated
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# start uvicorn on all interfaces, reload enabled for development
uvicorn backend_api.main:app --reload --host 0.0.0.0 --port 8000
