# Enzura AI - Project Structure

## 📁 Directory Structure

```
Enzura-ai/
│
├── frontend/                    # React Frontend Application
│   ├── src/
│   │   ├── components/         # React components
│   │   │   ├── Dashboard.jsx
│   │   │   ├── MyCalls.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── LandingPage.jsx
│   │   │   └── ... (other components)
│   │   ├── contexts/           # React contexts
│   │   │   └── AuthContext.jsx
│   │   ├── services/           # API services
│   │   │   └── api.js
│   │   ├── App.jsx             # Main app component
│   │   ├── index.js            # Entry point
│   │   └── index.css           # Global styles
│   ├── public/                 # Static assets
│   │   ├── index.html
│   │   └── logo.svg
│   ├── package.json            # Frontend dependencies
│   ├── tailwind.config.js      # Tailwind configuration
│   ├── postcss.config.js       # PostCSS configuration
│   └── vercel.json             # Vercel deployment config
│
├── backend/                     # FastAPI Backend Application
│   ├── app/
│   │   ├── routers/            # API route handlers
│   │   │   ├── auth.py         # Authentication routes
│   │   │   ├── calls.py        # Call management routes
│   │   │   ├── clients.py      # Client management routes
│   │   │   ├── insights.py     # Insights routes
│   │   │   └── ... (other routers)
│   │   ├── services/           # Business logic services
│   │   │   ├── s3_service.py
│   │   │   ├── processing_service.py
│   │   │   └── s3_monitoring_service.py
│   │   ├── models.py           # Database models
│   │   ├── database.py         # Database configuration
│   │   ├── auth.py             # Authentication utilities
│   │   └── main.py             # FastAPI app entry point
│   ├── migrations/              # Database migrations
│   │   └── add_performance_indexes.sql
│   ├── requirements.txt        # Python dependencies
│   ├── Procfile                # Deployment configuration
│   ├── runtime.txt             # Python version
│   ├── env.example             # Environment variables template
│   └── README.md               # Backend documentation
│
├── .gitignore                   # Git ignore rules
├── README.md                    # Main project documentation
├── HOSTING_GUIDE.md            # Deployment guide
├── QUICK_DEPLOY.md             # Quick deployment steps
└── PRE_PRODUCTION_CHECKLIST.md  # Pre-production checklist
```

## 🔄 Development Workflow

### Running Locally

1. **Start Backend**:
   ```bash
   cd backend
   venv\Scripts\activate  # Windows
   uvicorn app.main:app --reload
   ```

2. **Start Frontend** (in new terminal):
   ```bash
   cd frontend
   npm start
   ```

### Making Changes

- **Frontend**: Edit files in `frontend/src/`
- **Backend**: Edit files in `backend/app/`
- **Database**: Run migrations from `backend/migrations/`

## 📦 Deployment Structure

### Frontend Deployment (Vercel)
- Deploy from `frontend/` directory
- Build command: `npm run build`
- Output: `frontend/build/`

### Backend Deployment (Railway/Render)
- Deploy from `backend/` directory
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: Set in hosting platform

## 🔗 Key Files

### Frontend
- `frontend/src/App.jsx` - Main routing and app structure
- `frontend/src/services/api.js` - API client configuration
- `frontend/src/contexts/AuthContext.jsx` - Authentication state

### Backend
- `backend/app/main.py` - FastAPI application setup
- `backend/app/models.py` - Database models
- `backend/app/database.py` - Database connection
- `backend/app/routers/` - API endpoints

## 📝 Notes

- Frontend and backend are separate applications
- They communicate via REST API
- Both can be deployed independently
- Environment variables are managed separately

