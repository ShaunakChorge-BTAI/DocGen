#!/bin/bash
set -e

echo "=============================="
echo "  DocGen — Starting Services  "
echo "=============================="

# Start backend
echo ""
echo "► Starting FastAPI backend on http://localhost:8000 ..."
cd "$(dirname "$0")/backend"
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "► Starting React frontend on http://localhost:5173 ..."
cd "$(dirname "$0")/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend : http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" INT TERM
wait
