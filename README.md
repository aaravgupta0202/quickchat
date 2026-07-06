# QuickChat

QuickChat is a modern, premium, and temporary chat application. Rooms automatically expire after 1 hour, making it perfect for quick, disposable conversations without the hassle of permanent data storage.

## Features
- **Temporary Rooms**: Rooms and messages expire after 1 hour.
- **Real-time Chat**: See active users and typing indicators.
- **Premium UI**: Sleek dark mode, glassmorphism, and responsive design.
- **Customizable**: Change chat themes and room names on the fly.

## Tech Stack
- **Frontend**: Vanilla HTML/CSS/JS with TailwindCSS.
- **Backend**: FastAPI (Python).
- **Database**: PostgreSQL (via Neon DB) with SQLAlchemy.

## Local Setup

### Backend
1. Navigate to the `backend` directory.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` in the `backend` directory.
4. (Optional) Set up your PostgreSQL database URL in the `.env` file: `DATABASE_URL=postgresql://user:password@host/dbname`. If left blank, it automatically falls back to a local SQLite database for easy testing without setup.
5. Run the server: `uvicorn main:app --reload`

### Frontend
1. The frontend uses relative paths or proxies. For local development, you can open `frontend/index.html` directly in your browser, but you will need to update the `backend` variable in the JS scripts to `http://localhost:8000` for testing without Netlify's proxy.

## Deployment

### Frontend (Netlify)
Deploy the root repository to Netlify. The `netlify.toml` file automatically sets the publish directory to `frontend` and proxies `/api` requests to your backend URL.

### Backend (Render)
Deploy the `backend` directory as a Web Service on Render.
1. Connect your GitHub repository.
2. Ensure the build command is `pip install -r requirements.txt` and start command is `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Set the `DATABASE_URL` environment variable to your Neon DB connection string.
