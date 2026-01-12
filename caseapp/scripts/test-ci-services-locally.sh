#!/bin/bash

# Local CI Services Test Script
# This script simulates the GitHub Actions environment to test service startup locally
# and validates the Docker exec approach used in the CI pipeline

set -e

echo "🧪 Testing CI Services Locally - Docker Exec Approach Validation"
echo "=================================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function for exponential backoff retry (same as GitHub Actions)
retry_with_backoff() {
    local max_attempts=20
    local delay=3
    local attempt=1
    local command="$1"
    local service_name="$2"
    
    while [ $attempt -le $max_attempts ]; do
        print_status $BLUE "⏳ Attempt $attempt/$max_attempts: Checking $service_name..."
        
        if eval "$command"; then
            print_status $GREEN "✅ $service_name is ready!"
            return 0
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            print_status $RED "❌ $service_name failed to become ready after $max_attempts attempts"
            echo "🔍 Debugging $service_name status..."
            
            # Show Docker containers
            echo "Docker containers:"
            docker ps -a || true
            
            # Additional debugging for PostgreSQL
            if [ "$service_name" = "PostgreSQL" ]; then
                echo "PostgreSQL container logs:"
                POSTGRES_CONTAINER=$(docker ps -q --filter ancestor=postgres:15)
                if [ -n "$POSTGRES_CONTAINER" ]; then
                    docker logs "$POSTGRES_CONTAINER" 2>/dev/null | tail -30 || true
                    echo "Testing PostgreSQL connection via Docker exec:"
                    docker exec "$POSTGRES_CONTAINER" pg_isready -U postgres -d test_db || true
                else
                    echo "PostgreSQL container not found"
                fi
            fi
            
            # Additional debugging for Redis
            if [ "$service_name" = "Redis" ]; then
                echo "Redis container logs:"
                REDIS_CONTAINER=$(docker ps -q --filter ancestor=redis:7-alpine)
                if [ -n "$REDIS_CONTAINER" ]; then
                    docker logs "$REDIS_CONTAINER" 2>/dev/null | tail -30 || true
                    echo "Testing Redis connection via Docker exec:"
                    docker exec "$REDIS_CONTAINER" redis-cli ping || true
                else
                    echo "Redis container not found"
                fi
            fi
            
            return 1
        fi
        
        print_status $YELLOW "⏳ $service_name not ready, waiting ${delay}s before retry..."
        sleep $delay
        
        # Exponential backoff with max delay of 15 seconds
        if [ $delay -lt 15 ]; then
            delay=$((delay + 2))
        fi
        
        attempt=$((attempt + 1))
    done
}

# Cleanup function
cleanup() {
    print_status $YELLOW "🧹 Cleaning up test containers..."
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true
}

# Set trap for cleanup
trap cleanup EXIT

# Check Docker Compose command
DOCKER_COMPOSE_CMD="docker compose"
if ! command -v docker &> /dev/null; then
    print_status $RED "❌ Docker not found. Please install Docker Desktop."
    exit 1
fi

# Test docker compose vs docker-compose
if ! docker compose version &> /dev/null; then
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        print_status $RED "❌ Neither 'docker compose' nor 'docker-compose' found. Please install Docker Compose."
        exit 1
    fi
fi

print_status $GREEN "✅ Using Docker Compose command: $DOCKER_COMPOSE_CMD"

# Step 1: Create a test docker-compose file that matches GitHub Actions
print_status $BLUE "📝 Creating test docker-compose configuration..."

cat > docker-compose.test.yml << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: test_db
      POSTGRES_INITDB_ARGS: "--auth-host=scram-sha-256 --auth-local=scram-sha-256"
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d test_db"]
      interval: 3s
      timeout: 15s
      retries: 20
      start_period: 60s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 15s
      retries: 20
      start_period: 30s
EOF

# Step 2: Start services
print_status $BLUE "🚀 Starting test services (matching GitHub Actions configuration)..."
$DOCKER_COMPOSE_CMD -f docker-compose.test.yml up -d

# Step 3: Test the root cause issue - host vs container commands
print_status $BLUE "🔍 Testing the root cause: Host vs Container command availability..."

print_status $YELLOW "Testing host system commands (GitHub Actions approach):"

# Test if pg_isready is available on host
if command -v pg_isready &> /dev/null; then
    print_status $GREEN "✅ pg_isready available on host system"
    pg_isready -h localhost -p 5432 -U postgres -q && print_status $GREEN "✅ PostgreSQL reachable from host" || print_status $RED "❌ PostgreSQL not reachable from host"
else
    print_status $RED "❌ pg_isready NOT available on host system (GitHub Actions issue)"
fi

# Test if redis-cli is available on host
if command -v redis-cli &> /dev/null; then
    print_status $GREEN "✅ redis-cli available on host system"
    redis-cli -h localhost -p 6379 ping > /dev/null 2>&1 && print_status $GREEN "✅ Redis reachable from host" || print_status $RED "❌ Redis not reachable from host"
else
    print_status $RED "❌ redis-cli NOT available on host system (GitHub Actions issue)"
fi

print_status $YELLOW "Testing Docker exec commands (Fixed approach):"

# Wait a moment for containers to be ready
sleep 5

# Test PostgreSQL via Docker exec
POSTGRES_CONTAINER=$(docker ps -q --filter ancestor=postgres:15)
if [ -n "$POSTGRES_CONTAINER" ]; then
    print_status $GREEN "✅ PostgreSQL container found: $POSTGRES_CONTAINER"
    if docker exec "$POSTGRES_CONTAINER" pg_isready -U postgres -d test_db > /dev/null 2>&1; then
        print_status $GREEN "✅ PostgreSQL ready via Docker exec"
    else
        print_status $RED "❌ PostgreSQL not ready via Docker exec"
    fi
else
    print_status $RED "❌ PostgreSQL container not found"
fi

# Test Redis via Docker exec
REDIS_CONTAINER=$(docker ps -q --filter ancestor=redis:7-alpine)
if [ -n "$REDIS_CONTAINER" ]; then
    print_status $GREEN "✅ Redis container found: $REDIS_CONTAINER"
    if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
        print_status $GREEN "✅ Redis ready via Docker exec"
    else
        print_status $RED "❌ Redis not ready via Docker exec"
    fi
else
    print_status $RED "❌ Redis container not found"
fi

# Step 4: Wait for services using the NEW GitHub Actions logic (Docker exec)
print_status $BLUE "⏳ Testing NEW GitHub Actions approach (Docker exec)..."

# Wait for PostgreSQL with Docker exec
print_status $BLUE "🐘 Waiting for PostgreSQL to be ready via Docker exec..."
retry_with_backoff "docker exec \$(docker ps -q --filter ancestor=postgres:15) pg_isready -U postgres -d test_db > /dev/null 2>&1" "PostgreSQL"

# Wait for Redis with Docker exec
print_status $BLUE "🔴 Waiting for Redis to be ready via Docker exec..."
retry_with_backoff "docker exec \$(docker ps -q --filter ancestor=redis:7-alpine) redis-cli ping > /dev/null 2>&1" "Redis"

# Step 5: Additional connection tests
print_status $BLUE "🔍 Running additional connection tests..."

# Test PostgreSQL connection via Docker exec
print_status $BLUE "Testing PostgreSQL database connection via Docker exec..."
docker exec "$POSTGRES_CONTAINER" psql -U postgres -d test_db -c "SELECT 'PostgreSQL connection successful via Docker exec!' as status;"

# Test Redis connection via Docker exec
print_status $BLUE "Testing Redis key-value operations via Docker exec..."
docker exec "$REDIS_CONTAINER" redis-cli set test_key "Redis connection successful via Docker exec!"
docker exec "$REDIS_CONTAINER" redis-cli get test_key
docker exec "$REDIS_CONTAINER" redis-cli del test_key

# Step 6: Test the actual CI test command (if Python is available)
if command -v python3 &> /dev/null && [ -f "backend/tests/test_ci_basic.py" ]; then
    print_status $BLUE "🧪 Testing actual CI test execution..."

    # Set up Python environment (if not already set up)
    if [ ! -d "backend/venv" ]; then
        print_status $BLUE "📦 Setting up Python virtual environment..."
        cd backend
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r ../requirements.txt
        pip install pytest pytest-asyncio pytest-cov
        cd ..
    else
        print_status $BLUE "📦 Using existing Python virtual environment..."
        cd backend
        source venv/bin/activate
        cd ..
    fi

    # Run the actual test that GitHub Actions runs
    print_status $BLUE "🧪 Running backend tests (same as GitHub Actions)..."
    cd backend
    export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/test_db"
    export REDIS_URL="redis://localhost:6379"
    export SECRET_KEY="test-secret-key-for-ci"
    export ENABLE_AI_FEATURES="false"

    python -m pytest tests/test_ci_basic.py -v --tb=short

    cd ..
else
    print_status $YELLOW "⚠️  Skipping Python tests (Python3 or test file not available)"
fi

print_status $GREEN "🎉 All tests completed successfully!"
print_status $GREEN "✅ Docker exec approach should work in GitHub Actions"

# Step 7: Summary and recommendations
print_status $BLUE "📊 Summary and Recommendations:"
echo ""
echo "Root Cause Analysis:"
echo "- Host system commands (pg_isready, redis-cli) may not be available in GitHub Actions runners"
echo "- Docker exec commands work reliably as they execute inside the containers"
echo ""
echo "Fix Applied:"
echo "- Updated GitHub Actions workflow to use 'docker exec' instead of host commands"
echo "- This ensures commands are executed inside the containers where tools are available"
echo ""
echo "Expected Result:"
echo "- GitHub Actions should now pass the 'Wait for services to be ready' step"
echo "- Services will be properly validated before running tests"

print_status $GREEN "🎯 Local validation completed! GitHub Actions should now work correctly."