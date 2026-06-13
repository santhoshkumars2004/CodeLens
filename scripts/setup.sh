#!/bin/bash
# StackSense — One-Command Local Setup
set -e

echo "🧠 StackSense — Local Setup"
echo "================================"

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "❌ Git is required"; exit 1; }

echo "✅ Prerequisites check passed"

# Setup environment
if [ ! -f .env ]; then
  cp .env.example .env
  echo "📄 Created .env from .env.example"
  echo "⚠️  Please add your GROQ_API_KEY to .env"
fi

# Backend setup
echo ""
echo "🐍 Setting up backend..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -q
echo "✅ Backend dependencies installed"
cd ..

# Frontend setup
echo ""
echo "🌐 Setting up frontend..."
cd frontend
npm install -q
echo "✅ Frontend dependencies installed"
cd ..

echo ""
echo "================================"
echo "✅ Setup complete!"
echo ""
echo "To start development:"
echo "  Backend:  cd backend && source venv/bin/activate && uvicorn main:app --reload"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Or use Docker: docker-compose up --build"
echo ""
echo "⚠️  Don't forget to add your GROQ_API_KEY to .env!"
