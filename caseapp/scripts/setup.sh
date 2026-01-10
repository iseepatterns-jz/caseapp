#!/bin/bash

# Court Case Management System Setup Script

set -e

echo "🏛️  Setting up Court Case Management System..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p media/uploads
mkdir -p media/processed
mkdir -p media/thumbnails
mkdir -p media/previews
mkdir -p nginx/ssl

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Creating environment file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration before proceeding."
fi

# Generate SSL certificates for development (self-signed)
if [ ! -f nginx/ssl/cert.pem ]; then
    echo "🔐 Generating SSL certificates for development..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/key.pem \
        -out nginx/ssl/cert.pem \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
fi

# Install Python dependencies for infrastructure
echo "🐍 Installing Python dependencies..."
pip install -r requirements.txt
pip install -r infrastructure/requirements.txt

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install
cd infrastructure && npm install && cd ..

# Build Docker images
echo "🐳 Building Docker images..."
docker-compose build

# Initialize database
echo "🗄️  Initializing database..."
docker-compose up -d postgres redis
sleep 10

# Run database migrations
echo "🔄 Running database migrations..."
docker-compose run --rm backend alembic upgrade head

# Start all services
echo "🚀 Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check service health
echo "🏥 Checking service health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend service is healthy"
else
    echo "❌ Backend service is not responding"
fi

if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend service is healthy"
else
    echo "❌ Frontend service is not responding"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Services available at:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo "  API Documentation: http://localhost:8000/api/docs"
echo "  Database: localhost:5432"
echo "  Redis: localhost:6379"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop services: docker-compose down"
echo ""
echo "⚠️  Remember to:"
echo "  1. Configure your .env file with proper AWS credentials"
echo "  2. Set up your AWS services (S3, Textract, Comprehend, etc.)"
echo "  3. Configure your domain and SSL certificates for production"