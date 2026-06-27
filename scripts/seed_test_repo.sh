#!/bin/bash
# CodeLens — Seed a test repo for development
set -e

API_URL="${1:-http://localhost:8000}"
REPO_URL="${2:-https://github.com/tiangolo/fastapi}"

echo "🧪 Seeding test repository: $REPO_URL"
echo "📡 API: $API_URL"

# Check backend is running
echo "Checking backend health..."
curl -sf "$API_URL/health" > /dev/null || { echo "❌ Backend not running at $API_URL"; exit 1; }
echo "✅ Backend is healthy"

# Ingest repository
echo ""
echo "📥 Ingesting repository (this may take a few minutes)..."
RESULT=$(curl -sf -X POST "$API_URL/api/ingest" \
  -H "Content-Type: application/json" \
  -d "{\"repo_url\": \"$REPO_URL\"}")

echo ""
echo "✅ Ingestion complete!"
echo "$RESULT" | python3 -m json.tool

# Test a query
echo ""
echo "🔍 Testing a query..."
QUERY_RESULT=$(curl -sf -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d "{\"repo_id\": \"tiangolo/fastapi\", \"question\": \"How does routing work?\"}")

echo "$QUERY_RESULT" | python3 -m json.tool
echo ""
echo "✅ Test complete! Open http://localhost:3000 to use the UI."
