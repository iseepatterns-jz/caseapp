# Court Case Management System

A comprehensive legal case management platform with AI-powered document analysis, forensic email/text message analysis, and advanced timeline building capabilities.

## Project Structure

```
.
├── caseapp/                    # Main application directory
│   ├── backend/               # Python FastAPI backend
│   │   ├── api/              # API endpoints
│   │   ├── core/             # Core configuration and database
│   │   ├── models/           # SQLAlchemy models
│   │   ├── services/         # Business logic services
│   │   └── schemas/          # Pydantic schemas
│   ├── frontend/             # React TypeScript frontend
│   │   └── components/       # React components
│   ├── infrastructure/       # AWS CDK infrastructure code
│   ├── nginx/               # Nginx configuration
│   ├── scripts/             # Setup and utility scripts
│   ├── docker-compose.yml   # Docker services configuration
│   ├── Dockerfile          # Multi-stage Docker build
│   ├── requirements.txt    # Python dependencies
│   └── package.json        # Node.js dependencies
└── README.md               # This file
```

## Features

### 🏛️ Core Case Management

- Case timeline and milestone tracking
- Document management with version control
- Client communication portal
- Billing and time tracking
- Automated deadline reminders

### 🤖 AI-Powered Analysis

- **Amazon Textract** for document analysis
- **Amazon Comprehend** for natural language search
- **Automated case categorization** using AI
- **Court e-filing system integration**

### 🎥 Media Evidence Management

- **Audio/video evidence** upload and processing
- **Secure media sharing** with timeout controls
- **Real-time streaming** with range request support
- **Media annotations** and timestamps
- **Chain of custody** logging

### 📅 Advanced Timeline Building

- **Visual timeline builder** with evidence pinning
- **Collaboration features** with real-time editing
- **Export capabilities** (PDF, PNG, JSON)
- **Auto-detection** of timeline events from documents
- **Evidence correlation** with case events

### 🔍 Forensic Analysis

- **Email analysis** (.mbox, .eml, .pst files)
- **Text message analysis** (iPhone/Android backups)
- **WhatsApp database analysis**
- **Communication network mapping**
- **Sentiment analysis** and pattern detection
- **Deleted message recovery**

### 🤝 Collaboration & Sharing

- **Real-time collaboration** on timelines
- **Granular permissions** system
- **Secure sharing links** with expiration
- **Activity tracking** and audit logs
- **Comment system** on timeline events

## Quick Start

1. **Navigate to the application directory:**

   ```bash
   cd caseapp
   ```

2. **Run the setup script:**

   ```bash
   ./scripts/setup.sh
   ```

3. **Or start with Docker Compose:**

   ```bash
   docker-compose up -d
   ```

4. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs

## Technology Stack

### Backend

- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Database ORM with async support
- **PostgreSQL** - Primary database
- **Redis** - Caching and session management
- **Celery** - Background task processing

### Frontend

- **React** with TypeScript
- **Material-UI** - Component library
- **React Timeline** - Timeline visualization
- **Recharts** - Data visualization

### Infrastructure

- **AWS CDK** - Infrastructure as code
- **Docker** - Containerization
- **Nginx** - Reverse proxy and load balancer
- **AWS Services** - S3, Textract, Comprehend, OpenSearch

### AI & Analysis

- **spaCy** - Natural language processing
- **TextBlob** - Sentiment analysis
- **NetworkX** - Communication network analysis
- **scikit-learn** - Machine learning
- **FFmpeg** - Media processing

## Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- AWS CLI (for deployment)

### Local Development

```bash
cd caseapp

# Backend
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Deployment

```bash
cd caseapp/infrastructure
cdk deploy
```

## Security & Compliance

- **End-to-end encryption** for sensitive documents
- **Multi-factor authentication**
- **HIPAA/SOC 2 compliance** ready
- **Audit trails** for all data access
- **Chain of custody** for evidence
- **Role-based access control**

## License

MIT License - see LICENSE file for details.

## Support

For support and documentation, please refer to the individual component README files in the caseapp directory.
