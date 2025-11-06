# Enzura AI Backend

FastAPI backend for Enzura AI call analytics platform.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install ffmpeg (required for pydub):
   - **Windows**: Download from https://ffmpeg.org/download.html or use `choco install ffmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) or `sudo yum install ffmpeg` (CentOS/RHEL)

3. Copy environment variables:
```bash
cp env.example .env
```

4. Update `.env` with your actual API keys and database credentials.

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
API documentation at `http://localhost:8000/docs`
