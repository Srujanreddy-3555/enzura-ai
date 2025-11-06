# Enzura AI - Call Analytics Platform

A comprehensive call analytics platform built with React (Frontend) and FastAPI (Backend) that provides AI-powered insights into sales calls.

## 🏗️ Project Structure

```
Enzura-ai/
├── frontend/          # React frontend application
│   ├── src/          # Source code
│   ├── public/       # Static files
│   └── package.json  # Frontend dependencies
│
├── backend/          # FastAPI backend application
│   ├── app/         # Application code
│   ├── migrations/  # Database migrations
│   └── requirements.txt
│
└── README.md        # This file
```

## 🚀 Quick Start

### Prerequisites
- Node.js 16+ (for frontend)
- Python 3.11+ (for backend)
- PostgreSQL database

### Frontend Setup

```bash
cd frontend
npm install
npm start
```

Frontend will run at: `http://localhost:3000`

### Backend Setup

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Create .env file from env.example
cp env.example .env
# Edit .env with your configuration

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will run at: `http://localhost:8000`  
API docs at: `http://localhost:8000/docs`

## 📚 Documentation

- **[HOSTING_GUIDE.md](./HOSTING_GUIDE.md)** - Complete hosting and deployment guide
- **[QUICK_DEPLOY.md](./QUICK_DEPLOY.md)** - Step-by-step deployment instructions
- **[PRE_PRODUCTION_CHECKLIST.md](./PRE_PRODUCTION_CHECKLIST.md)** - Pre-production security and optimization checklist

## 🎯 Features

- **AI-Powered Call Analysis**: OpenAI integration for call insights
- **Multi-Tenant Architecture**: Support for Admin, Client, and Sales Rep roles
- **Real-time Analytics**: Dashboard with call statistics and metrics
- **Call Management**: Upload, process, and manage call recordings
- **Leaderboard**: Track sales rep performance
- **Client Management**: Admin tools for managing clients and users
- **S3 Integration**: Automatic processing of uploaded calls
- **Responsive Design**: Modern UI built with React and Tailwind CSS

## 🛠️ Tech Stack

### Frontend
- React 18
- React Router DOM
- Tailwind CSS
- Axios

### Backend
- FastAPI
- SQLModel / SQLAlchemy
- PostgreSQL
- OpenAI API
- AWS S3 (Boto3)
- JWT Authentication

## 📦 Deployment

### Recommended Setup
- **Frontend**: Vercel (Free tier available)
- **Backend**: Railway or Render (Free tier available)
- **Database**: Railway PostgreSQL or Neon (Free tier available)

See [HOSTING_GUIDE.md](./HOSTING_GUIDE.md) for detailed deployment instructions.

## 🔐 Environment Variables

### Backend (`backend/.env`)
```
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o
DATABASE_URL=postgresql://...
SECRET_KEY=your-secret-key
ENVIRONMENT=production
CORS_ORIGINS=https://your-frontend-domain.com
```

### Frontend (`frontend/.env`)
```
REACT_APP_API_URL=http://localhost:8000/api
```

## 📝 License

Private - All rights reserved

## 👥 Support

For deployment help, see the documentation files or check the troubleshooting sections in the hosting guides.
