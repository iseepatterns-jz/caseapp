# Getting Started with Court Case Management System

## 🚀 Quick Setup

### Option 1: Docker Setup (Recommended)

```bash
# Navigate to the application directory
cd caseapp

# Run the automated setup script
./scripts/setup.sh

# This will:
# - Install all dependencies
# - Build Docker images
# - Start all services
# - Initialize the database
# - Set up SSL certificates
```

### Option 2: Manual Setup

```bash
cd caseapp

# Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-media.txt

# Install Node.js dependencies
npm install
cd infrastructure && npm install && cd ..

# Start services with Docker Compose
docker-compose up -d

# Or start individual services
# Backend
cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend (in another terminal)
cd frontend && npm run dev
```

## 🌐 Access Points

Once setup is complete, you can access:

- **Frontend Application**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs
- **Interactive API**: http://localhost:8000/api/redoc

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key configurations:

- **AWS credentials** for AI services
- **Database connection** strings
- **JWT secret keys**
- **File upload limits**
- **Email/SMS service credentials**

### AWS Services Setup

The system uses several AWS services:

1. **S3 Buckets** - Document and media storage
2. **Textract** - Document analysis
3. **Comprehend** - Natural language processing
4. **OpenSearch** - Full-text search
5. **Cognito** - User authentication
6. **RDS** - Database (for production)

## 📊 First Steps

### 1. Create Your First Case

- Navigate to the Cases section
- Click "New Case"
- Fill in case details
- Upload initial documents

### 2. Build a Timeline

- Open your case
- Go to the Timeline tab
- Click "Add Event" to create timeline entries
- Use "Pin Evidence" to attach documents/media to events

### 3. Upload Forensic Data

- Go to Forensic Analysis
- Click "Upload Data"
- Select your .db, .mbox, or other forensic files
- Wait for AI analysis to complete

### 4. Collaborate with Team

- Click "Share" on any timeline
- Add team members with appropriate permissions
- Use real-time collaboration features

## 🔍 Key Features to Explore

### Timeline Building

- **Visual timeline** with drag-and-drop
- **Evidence pinning** to specific events
- **Auto-detection** of events from documents
- **Export** to PDF, PNG, or JSON

### Forensic Analysis

- **Email analysis** from .mbox files
- **Text message** extraction from phone backups
- **Communication networks** visualization
- **Sentiment analysis** of conversations

### Media Evidence

- **Video/audio** upload with streaming
- **Secure sharing** with expiration
- **Annotations** and timestamps
- **Chain of custody** tracking

### AI-Powered Features

- **Document analysis** with Textract
- **Smart search** with Comprehend
- **Case categorization** automation
- **Evidence correlation** suggestions

## 🛠️ Development

### Backend Development

```bash
cd backend

# Install dependencies
pip install -r ../requirements.txt

# Run with hot reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Format code
black . && isort . && flake8
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm test
```

### Infrastructure Development

```bash
cd infrastructure

# Install CDK dependencies
npm install

# Deploy to AWS
cdk bootstrap  # First time only
cdk deploy

# Destroy infrastructure
cdk destroy
```

## 📚 Documentation

- **API Documentation**: Available at `/api/docs` when running
- **Component Documentation**: In each component directory
- **Database Schema**: See `backend/models/` directory
- **Infrastructure**: See `infrastructure/` directory

## 🆘 Troubleshooting

### Common Issues

**Port Already in Use**

```bash
# Kill processes on ports 3000 or 8000
lsof -ti:3000 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

**Database Connection Issues**

```bash
# Reset database
docker-compose down -v
docker-compose up -d postgres
```

**Permission Issues**

```bash
# Fix file permissions
chmod +x scripts/setup.sh
```

**AWS Credentials**

```bash
# Configure AWS CLI
aws configure
# Or set environment variables in .env
```

### Getting Help

1. Check the logs: `docker-compose logs -f`
2. Verify services: `docker-compose ps`
3. Check API health: `curl http://localhost:8000/health`
4. Review configuration in `.env` file

## 🎯 Next Steps

1. **Explore the Timeline Builder** - Create visual case chronologies
2. **Try Forensic Analysis** - Upload email or text message data
3. **Set up Collaboration** - Invite team members to work together
4. **Configure AI Services** - Connect AWS services for enhanced features
5. **Customize the System** - Modify components for your specific needs

---

**Need help?** Check the main README.md or create an issue in the repository.
