# LEMO Backend

This Repo is backend service built using FastAPI, providing endpoints for session management, authentication, chat messaging, and advanced product and page context recommendations using modern machine learning models.

---

## Overview

This backend uses FastAPI for web APIs, Prisma ORM for PostgreSQL, Redis for fast data access, and is enabled for interaction with Gemini LLMs, product recommendation, and session-based chat.

---

## Prerequisites

- Python 3.10+ recommended
- Git
- PostgreSQL database running and accessible
- Redis server running and accessible

---

## Installation & Setup

Follow the steps below to set up and launch LEMO Backend on your machine.

### 1. Clone the Repository

```sh
git clone https://github.com/ethonline25-lemo/lemo-fastapi.git
cd lemo-fastapi
```

### 2. Create a Virtual Environment

```sh
# Windows
python -m venv venv

# macOS/Linux
python3 -m venv venv
```

### 3. Activate the Virtual Environment

```sh
# Windows (cmd)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate
```

### 4. Install All Dependencies

```sh
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Generate Prisma Client

You must run this every time you change `prisma/schema.prisma`:

```sh
prisma generate
```

You may also need to initialize the database schema/migrations (if configured):
```sh
# Optional, only if you use prisma migrations
prisma migrate deploy
```
(_Check your schema setup and migrations in `/prisma` if needed._)

---

## Environment Variables

Create a `.env` file in your project root with the following required variables:

```ini
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=your-gemini-api-key
DATABASE_URL=postgresql://user:password@localhost:5432/yourdb
```

- Adjust values according to your infrastructure.
- Make sure your database and Redis are accessible as per these configurations.

---

## Running the Application

Once everything is set up, start the development server using:

```sh
python run.py
```

The FastAPI app will be available at: `http://localhost:8000`

- The main app entrypoint is in `main.py`.
- The auto-reload server is used for local development.

---

## Common Issues / Notes

- **Database schema initialization:** If you get database errors, ensure your schema is migrated using `prisma migrate deploy`.
- **Dependency errors:** Double-check your virtual environment is activated and all pip dependencies installed.
- **Missing environment variables:** The backend will not work without setting up all `.env` variables above.
- **Prisma/Python ORM:** You need `prisma generate` if you update the models.

---

## Project Structure

- `cases/`, `context_retrivers/`, `controllers/`, `helpers/` – Core backend logic
- `routes/` – API routing
- `prisma/` – Database schema & migrations config
- `main.py` – FastAPI application factory
- `run.py` – Launch script for uvicorn server

---

## Contributing

Contributions and ideas welcome! Fork, open issues, or submit pull requests if you find bugs or want to add features.
