# Court Case Management System

A comprehensive legal case management platform built on AWS with AI-powered document analysis, forensic email/text message analysis, and advanced timeline building capabilities.

## 🎯 Key Features

### Core Functionality

- **Case timeline and milestone tracking** with visual timeline builder
- **Document management** with version control and AI analysis
- **Calendar integration** for court dates and deadlines
- **Client communication portal** with secure messaging
- **Billing and time tracking** with automated invoicing
- **Automated deadline reminders** and notifications

### 🤖 AI-Powered Features

- **Amazon Textract** for intelligent document analysis
- **Amazon Comprehend** for natural language search and insights
- **Automated case categorization** using machine learning
- **Court e-filing system integration** for seamless filing
- **Smart evidence correlation** with timeline events

### 🎥 Advanced Media Evidence

- **Audio/video evidence** upload with forensic integrity
- **Secure media sharing** with timeout and access controls
- **Real-time streaming** with range request support for large files
- **Media annotations** and timestamp marking
- **Chain of custody** logging for legal compliance
- **Watermarking** and download restrictions

### 📅 Timeline Building with Evidence Pinning

- **Visual timeline builder** with drag-and-drop interface
- **Evidence pinning** - attach documents/media to specific events
- **Real-time collaboration** with team members
- **Export capabilities** (PDF reports, PNG charts, JSON data)
- **Auto-detection** of timeline events from case documents
- **Relevance scoring** and context notes for evidence

### 🔍 Forensic Digital Analysis

- **Email analysis** (.mbox, .eml, .pst archives)
- **Text message analysis** (iPhone/Android backup databases)
- **WhatsApp database** forensic extraction
- **Communication network mapping** with relationship analysis
- **Sentiment analysis** and emotional pattern detection
- **Deleted message recovery** with forensic integrity
- **Metadata preservation** for legal admissibility

### 🤝 Collaboration & Security

- **Real-time collaboration** on timelines and documents
- **Granular permissions** system (view, edit, share, pin evidence)
- **Secure sharing links** with expiration and view limits
- **Activity tracking** and comprehensive audit logs
- **Comment system** on timeline events and evidence
- **Multi-factor authentication** and SSO integration

## 🏗️ Architecture

**Frontend**: Next.js with TypeScript and Material-UI
**Backend**: Python FastAPI with async SQLAlchemy
**Database**: Amazon RDS PostgreSQL with read replicas
**Cache**: Amazon ElastiCache Redis
**Search**: Amazon OpenSearch for full-text search
**Storage**: Amazon S3 with lifecycle policies
**AI Services**: Textract, Comprehend, Bedrock
**Infrastructure**: AWS CDK for Infrastructure as Code

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Run the setup script
./scripts/setup.sh

# Or manually with Docker Compose
docker-compose up -d
```

### Manual Setup

```bash
# Install dependencies
npm run setup

# Start development servers
npm run dev
```

**Services will be available at:**

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs
- Database: localhost:5432
- Redis: localhost:6379

## 📁 Project Structure

```
caseapp/
├── backend/                    # Python FastAPI application
│   ├── api/v1/endpoints/      # API route handlers
│   ├── core/                  # Configuration and database setup
│   ├── models/                # SQLAlchemy database models
│   ├── services/              # Business logic services
│   └── schemas/               # Pydantic request/response schemas
├── frontend/                   # Next.js React application
│   └── components/            # React components
│       ├── timeline/          # Timeline building components
│       └── forensic/          # Forensic analysis components
├── infrastructure/            # AWS CDK infrastructure code
├── nginx/                     # Nginx configuration
├── scripts/                   # Setup and utility scripts
├── docker-compose.yml         # Multi-service Docker setup
├── Dockerfile                 # Multi-stage container build
└── requirements.txt           # Python dependencies
```

## 🔧 Technology Stack

### Backend Technologies

- **FastAPI** - Modern Python web framework with automatic API docs
- **SQLAlchemy** - Async ORM with PostgreSQL
- **Celery** - Background task processing
- **spaCy** - Natural language processing
- **NetworkX** - Communication network analysis
- **FFmpeg** - Media processing and analysis

### Frontend Technologies

- **React** with TypeScript for type safety
- **Material-UI** - Professional component library
- **React Timeline** - Interactive timeline visualization
- **Recharts** - Data visualization and analytics
- **React Beautiful DnD** - Drag and drop interactions

### Infrastructure & DevOps

- **AWS CDK** - Infrastructure as Code
- **Docker** - Containerization with multi-stage builds
- **Nginx** - Reverse proxy with media streaming support
- **PostgreSQL** - Primary database with JSONB support
- **Redis** - Caching and real-time features

### AI & Analysis Services

- **Amazon Textract** - Document text and form extraction
- **Amazon Comprehend** - Natural language understanding
- **Amazon Bedrock** - Large language model integration
- **TextBlob** - Sentiment analysis
- **scikit-learn** - Machine learning and clustering

## 🔒 Security & Compliance

### Data Protection

- **End-to-end encryption** for sensitive legal documents
- **At-rest encryption** for all stored data
- **In-transit encryption** with TLS 1.3
- **Key management** with AWS KMS

### Access Control

- **Multi-factor authentication** required
- **Role-based permissions** with granular controls
- **Session management** with secure tokens
- **API rate limiting** and DDoS protection

### Legal Compliance

- **HIPAA compliance** for sensitive client data
- **SOC 2 Type II** security controls
- **Chain of custody** for digital evidence
- **Audit trails** for all data access and modifications
- **Data retention** policies with automated archival

## 📊 Forensic Analysis Capabilities

### Supported Data Sources

- **iPhone Backups** - SMS, iMessage, contacts, call logs
- **Android Backups** - Text messages, call history, app data
- **Email Archives** - .mbox, .eml, .pst with full header analysis
- **WhatsApp Databases** - Chat history, media, contact analysis
- **Generic Databases** - SQLite and other forensic formats

### Analysis Features

- **Sentiment Analysis** - Emotional tone detection across communications
- **Network Mapping** - Visual relationship graphs between contacts
- **Pattern Detection** - Unusual communication patterns and anomalies
- **Timeline Reconstruction** - Chronological message flow analysis
- **Deleted Data Recovery** - Forensically sound extraction methods
- **Metadata Preservation** - Complete header and timestamp analysis

## 🚀 Deployment

### AWS Deployment

```bash
cd infrastructure
npm install
cdk bootstrap
cdk deploy
```

### Local Development

```bash
# Backend
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## 📈 Performance & Scalability

- **Horizontal scaling** with ECS Fargate
- **Database read replicas** for improved performance
- **CDN integration** with CloudFront
- **Caching strategies** with Redis and application-level caching
- **Background processing** with Celery for heavy operations
- **Media streaming** optimized for large video files

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For technical support, feature requests, or bug reports:

- Create an issue in the GitHub repository
- Check the API documentation at `/api/docs`
- Review the component documentation in each directory

---

**Built with ❤️ for legal professionals who need powerful, secure, and intelligent case management tools.**
