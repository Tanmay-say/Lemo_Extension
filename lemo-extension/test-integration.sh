#!/bin/bash

echo "🧪 LEMO Extension - Integration Tests"
echo "======================================"
echo ""

# Test 1: Backend Health Check
echo "1️⃣  Testing Backend Health Check..."
HEALTH_CHECK=$(curl -s http://localhost:8001/)
if echo "$HEALTH_CHECK" | grep -q "Hello, World"; then
    echo "   ✅ Backend is running"
else
    echo "   ❌ Backend is not responding"
    exit 1
fi
echo ""

# Test 2: Database Connection
echo "2️⃣  Testing Database Connection..."
DB_TEST=$(sudo -u postgres psql -d lemo_db -c "SELECT COUNT(*) FROM users;" 2>&1)
if echo "$DB_TEST" | grep -q "count"; then
    echo "   ✅ Database is accessible"
else
    echo "   ❌ Database connection failed"
fi
echo ""

# Test 3: Redis Connection
echo "3️⃣  Testing Redis Connection..."
REDIS_TEST=$(redis-cli ping 2>&1)
if echo "$REDIS_TEST" | grep -q "PONG"; then
    echo "   ✅ Redis is running"
else
    echo "   ❌ Redis is not responding"
fi
echo ""

# Test 4: Create Test User
echo "4️⃣  Testing User Creation API..."
USER_CREATE=$(curl -s -X POST http://localhost:8001/auth/0xTESTWALLET123456 \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@lemo.ai",
    "firstName": "Test",
    "lastName": "User"
  }' 2>&1)

if echo "$USER_CREATE" | grep -q "success"; then
    echo "   ✅ User creation API working"
else
    if echo "$USER_CREATE" | grep -q "already exists"; then
        echo "   ✅ User creation API working (user already exists)"
    else
        echo "   ⚠️  User creation API response: $USER_CREATE"
    fi
fi
echo ""

# Test 5: Authenticate User
echo "5️⃣  Testing User Authentication API..."
USER_AUTH=$(curl -s http://localhost:8001/auth/0xTESTWALLET123456 2>&1)
if echo "$USER_AUTH" | grep -q "success"; then
    echo "   ✅ User authentication API working"
else
    echo "   ⚠️  Authentication response: $USER_AUTH"
fi
echo ""

# Test 6: Extension Build
echo "6️⃣  Checking Extension Build..."
if [ -d "/app/dist" ] && [ -f "/app/dist/manifest.json" ]; then
    echo "   ✅ Extension built successfully"
    echo "   📦 Load extension from: /app/dist/"
else
    echo "   ❌ Extension build not found"
fi
echo ""

# Test 7: Supervisor Status
echo "7️⃣  Checking Services Status..."
BACKEND_STATUS=$(supervisorctl status backend 2>&1)
if echo "$BACKEND_STATUS" | grep -q "RUNNING"; then
    echo "   ✅ Backend service is running"
else
    echo "   ❌ Backend service is not running"
fi
echo ""

# Summary
echo "======================================"
echo "📊 Test Summary"
echo "======================================"
echo ""
echo "🎯 Core Services:"
echo "   • Backend API: http://localhost:8001"
echo "   • PostgreSQL: localhost:5432"
echo "   • Redis: localhost:6379"
echo ""
echo "📁 Extension Location: /app/dist/"
echo ""
echo "🔗 How to Load Extension:"
echo "   1. Open Chrome: chrome://extensions/"
echo "   2. Enable 'Developer mode'"
echo "   3. Click 'Load unpacked'"
echo "   4. Select: /app/dist/"
echo ""
echo "✅ Integration tests complete!"
