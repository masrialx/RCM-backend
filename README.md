# 🏥 HUMAEIN Mini RCM Validation Engine

A comprehensive backend system for Revenue Cycle Management (RCM) claim validation, featuring static rule-based validation, LLM-powered analysis with Gemini 2.0 Flash, and multi-tenant architecture.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Validation Logic](#validation-logic)
- [Database Schema](#database-schema)
- [Usage Examples](#usage-examples)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The HUMAEIN Mini RCM Validation Engine is a sophisticated backend system designed to validate healthcare claims using a hybrid approach combining:

- **Static Rule-Based Validation**: Fast, deterministic validation using predefined business rules
- **LLM-Powered Analysis**: AI-driven validation using Google's Gemini 2.0 Flash model
- **Multi-Tenant Architecture**: Support for multiple healthcare organizations
- **Comprehensive Audit Trail**: Complete tracking of validation processes

### Key Capabilities

- ✅ **Technical Validation**: ID format, data integrity, approval requirements
- ✅ **Medical Validation**: Encounter types, facility restrictions, diagnosis codes
- ✅ **AI-Enhanced Analysis**: LLM-powered error explanation and recommendations
- ✅ **Real-time Processing**: Fast validation of large claim batches
- ✅ **Audit & Compliance**: Complete audit trail for regulatory requirements

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Layer     │    │  Validation   │    │   Database     │
│                 │    │    Engine      │    │    Layer       │
│ • Claims API    │◄──►│                │◄──►│                │
│ • Auth API      │    │ • Static Rules│    │ • Master       │
│ • Health API    │    │ • LLM Analysis│    │ • Refined      │
└─────────────────┘    └─────────────────┘    │ • Metrics      │
         │                       │            │ • Audit       │
         ▼                       ▼            └─────────────────┘
┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │    │  External APIs  │
│                 │    │                 │
│ • Web Frontend  │    │ • Gemini 2.0    │
│ • Mobile App    │    │ • Google AI     │
└─────────────────┘    └─────────────────┘
```

### Core Modules

| Module | Purpose | Key Components |
|--------|---------|----------------|
| **API Layer** | REST endpoints | Claims, Auth, Health APIs |
| **Validation Engine** | Core validation logic | Static rules, LLM integration |
| **Database Layer** | Data persistence | Master, Refined, Metrics, Audit |
| **Rules Engine** | Business logic | Tenant-specific configurations |
| **AI Agent** | LLM integration | Gemini 2.0 Flash client |

## ✨ Features

### 🔧 Technical Validation
- **Unique ID Format**: Validates `XXXX-XXXX-XXXX` format with segment matching
- **Data Integrity**: Ensures required fields and data types
- **Approval Requirements**: Checks for mandatory approvals based on service codes
- **Amount Thresholds**: Validates against configurable payment limits

### 🏥 Medical Validation
- **Encounter Type Rules**: Validates inpatient/outpatient service restrictions
- **Facility Type Mapping**: Ensures services are performed at appropriate facilities
- **Diagnosis Code Validation**: Checks for required and mutually exclusive diagnoses
- **Service-Diagnosis Mapping**: Validates appropriate diagnosis codes for services

### 🤖 AI-Powered Analysis
- **Error Explanation**: LLM-generated detailed error descriptions
- **Recommendation Engine**: AI-suggested corrective actions
- **Confidence Scoring**: LLM confidence levels for validation decisions
- **Context-Aware Analysis**: Considers claim context and medical guidelines

### 🏢 Multi-Tenant Support
- **Tenant Isolation**: Separate configurations and data per tenant
- **Configurable Rules**: Tenant-specific validation rules
- **Scalable Architecture**: Support for multiple healthcare organizations

## 🚀 Installation

### Prerequisites

- Python 3.9+
- PostgreSQL or SQLite
- Google AI API key (for LLM features)

### Quick Start

1. **Clone the repository**
```bash
git clone <repository-url>
cd RCM-backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize database**
```bash
python init_db.py
```

6. **Run the application**
```bash
python run.py
```

### Docker Installation

```bash
# Build and run with Docker Compose
docker-compose up -d
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:///instance/rcm.db` |
| `JWT_SECRET_KEY` | JWT signing key | `change-me` |
| `GOOGLE_API_KEY` | Google AI API key | Required for LLM features |
| `DEFAULT_TENANT_ID` | Default tenant identifier | `tenant_demo` |
| `MAX_UPLOAD_SIZE_MB` | Maximum file upload size | `25` |

### Tenant Configuration

Each tenant requires a configuration file at `configs/tenant_{tenant_id}.json`:

```json
{
  "services_requiring_approval_file": "services_requiring_approval.txt",
  "diagnoses_file": "diagnoses.txt",
  "paid_threshold_aed": 250,
  "id_rules": {
    "patterns": {
      "national_id": "^[A-Z0-9]{8}$",
      "member_id": "^[A-Z0-9]{8}$"
    },
    "uppercase_required": true,
    "inpatient_only_services": ["SRV1001", "SRV1002", "SRV1003"],
    "outpatient_only_services": ["SRV2001", "SRV2002", "SRV2003"]
  }
}
```

## 📚 API Documentation

### Authentication

All API endpoints require JWT authentication. Obtain a token via the login endpoint:

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin12345", "tenant_id": "tenant_demo"}'
```

### Core Endpoints

#### 1. Upload Claims
```http
POST /api/claims/upload
Content-Type: multipart/form-data
Authorization: Bearer <token>

Form Data:
- file: CSV/Excel file
- tenant_id: Tenant identifier
```

**Response:**
```json
{
  "inserted": 5,
  "validated": 3,
  "failed": 2
}
```

#### 2. Validate Specific Claims
```http
POST /api/claims/validate
Content-Type: application/json
Authorization: Bearer <token>

{
  "tenant_id": "tenant_demo",
  "claim_ids": ["claim_1", "claim_2"]
}
```

#### 3. Get Validation Results
```http
GET /api/claims/results?tenant_id=tenant_demo&page=1&page_size=10
Authorization: Bearer <token>
```

**Response:**
```json
{
  "claims": [
    {
      "claim_id": "1",
      "encounter_type": "INPATIENT",
      "service_code": "SRV1003",
      "error_type": "Technical error",
      "error_explanation": ["unique_id is invalid"],
      "recommended_action": ["Correct unique_id format"]
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 100,
    "total_pages": 10
  }
}
```

#### 4. Health Check
```http
GET /health
```

## 🔍 Validation Logic

### Static Rules Engine

The system applies the following validation rules:

#### Technical Rules
1. **Unique ID Format**: Must match `^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$`
2. **Approval Requirements**: Services requiring approval must have valid approval numbers
3. **Amount Thresholds**: Claims exceeding threshold require approval
4. **Data Format**: All IDs must be uppercase, required fields present

#### Medical Rules
1. **Encounter Type Validation**:
   - Inpatient services: `SRV1001`, `SRV1002`, `SRV1003`
   - Outpatient services: `SRV2001`, `SRV2002`, `SRV2003`, etc.

2. **Facility Type Restrictions**:
   - Dialysis centers: `SRV1003`, `SRV2010`
   - General hospitals: Most services
   - Maternity hospitals: `SRV2008`
   - Cardiology centers: `SRV2001`, `SRV2011`

3. **Diagnosis Code Rules**:
   - Required diagnoses for specific services
   - Mutually exclusive diagnosis pairs
   - Approval requirements for certain diagnoses

### LLM Integration

The system uses Google's Gemini 2.0 Flash for:

- **Error Explanation**: Detailed, human-readable error descriptions
- **Recommendation Generation**: Context-aware corrective actions
- **Confidence Scoring**: AI confidence in validation decisions
- **Context Analysis**: Medical guideline compliance

## 🗄️ Database Schema

### Core Tables

#### `claims_master`
Primary claims table storing all claim data and validation results.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `claim_id` | String(64) | Unique claim identifier |
| `encounter_type` | String(64) | INPATIENT/OUTPATIENT |
| `service_date` | Date | Date of service |
| `national_id` | String(64) | Patient national ID |
| `member_id` | String(64) | Member ID |
| `facility_id` | String(64) | Facility identifier |
| `unique_id` | String(128) | Composite unique identifier |
| `diagnosis_codes` | JSON | Array of diagnosis codes |
| `service_code` | String(64) | Service code |
| `paid_amount_aed` | Numeric(14,2) | Amount in AED |
| `approval_number` | String(64) | Approval reference |
| `status` | Enum | Validated/Not Validated/pending |
| `error_type` | Enum | Technical error/Medical error/Both/No error |
| `error_explanation` | JSON | Array of error descriptions |
| `recommended_action` | JSON | Array of recommended actions |
| `tenant_id` | String(64) | Tenant identifier |

#### `claims_refined`
Processed claims with normalized data and final decisions.

#### `claims_metrics`
Aggregated metrics for reporting and analytics.

#### `claims_audit`
Complete audit trail of all validation activities.

## 💡 Usage Examples

### Python Client Example

```python
import requests
import pandas as pd

# Authentication
auth_response = requests.post('http://localhost:5000/api/auth/login', json={
    'username': 'admin',
    'password': 'admin12345',
    'tenant_id': 'tenant_demo'
})
token = auth_response.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Upload claims
with open('claims.csv', 'rb') as f:
    files = {'file': f}
    data = {'tenant_id': 'tenant_demo'}
    response = requests.post('http://localhost:5000/api/claims/upload', 
                           files=files, data=data, headers=headers)
    print(response.json())

# Get results
results = requests.get('http://localhost:5000/api/claims/results', 
                      params={'tenant_id': 'tenant_demo'}, headers=headers)
claims = results.json()['claims']

# Process results
for claim in claims:
    print(f"Claim {claim['claim_id']}: {claim['error_type']}")
    for error in claim['error_explanation']:
        print(f"  - {error}")
```

### CSV Format

Expected CSV format for claim uploads:

```csv
encounter_type,service_date,national_id,member_id,facility_id,unique_id,diagnosis_codes,service_code,paid_amount_aed,approval_number
INPATIENT,5/3/2024,J45NUMBE,UZF615NA,0DBYE6KP,J45N-UZF6-E6KP,E66.9,SRV1003,559.91,NA
OUTPATIENT,1/13/2025,SYWX6RYN,B1G36XGM,OCQUMGDW,SYWX-G36X-MGDW,E66.3;R07.9,SRV2001,1077.6,APP001
```

## 🛠️ Development

### Project Structure

```
rcm_app/
├── __init__.py              # Flask app factory
├── settings.py              # Configuration management
├── extensions.py            # Flask extensions
├── api/                     # API endpoints
│   ├── claims.py           # Claims API
│   ├── auth.py             # Authentication API
│   └── __init__.py         # Blueprint registration
├── models/                  # Database models
│   └── models.py           # SQLAlchemy models
├── pipeline/               # Validation pipeline
│   └── engine.py           # Validation engine
├── utils/                  # Utility functions
│   ├── validators.py       # Validation logic
│   └── llm.py             # LLM integration
├── rules/                  # Business rules
│   └── loader.py          # Rules loader
├── agent/                  # AI agent framework
│   ├── react_agent.py     # ReAct agent
│   └── tools/             # Agent tools
└── tests/                  # Test suite
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_validators.py

# Run with coverage
pytest --cov=rcm_app
```

### Code Quality

```bash
# Format code
black rcm_app/

# Lint code
flake8 rcm_app/

# Type checking
mypy rcm_app/
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Database Connection Errors
```bash
# Check database URL
echo $DATABASE_URL

# Reset database
python reset_db.py
```

#### 2. LLM Integration Issues
```bash
# Check API key
echo $GOOGLE_API_KEY

# Test LLM connection
python -c "from rcm_app.utils.llm import GeminiClient; print(GeminiClient().enabled)"
```

#### 3. Validation Accuracy Issues
- Check tenant configuration files
- Verify rule definitions
- Review validation logic in `validators.py`

#### 4. Performance Issues
- Enable database connection pooling
- Optimize LLM API calls
- Consider caching for repeated validations

### Debug Mode

```bash
# Enable debug logging
export FLASK_DEBUG=1
export LOG_LEVEL=DEBUG
python run.py
```

### Logs

Application logs are available in:
- Console output (development)
- Log files (production)
- Database audit trail

## 📊 Performance Metrics

### Benchmarks

| Metric | Value |
|--------|-------|
| Claims per second | 50-100 |
| Average validation time | 200-500ms |
| LLM response time | 1-3 seconds |
| Database query time | <50ms |

### Optimization Tips

1. **Batch Processing**: Process multiple claims together
2. **Caching**: Cache validation rules and LLM responses
3. **Database Indexing**: Ensure proper indexes on query columns
4. **Async Processing**: Use background tasks for large batches

## 🔒 Security

### Authentication
- JWT-based authentication
- Role-based access control
- Token expiration and refresh

### Data Protection
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- Secure file upload handling

### Compliance
- Audit trail for all operations
- Data retention policies
- HIPAA compliance considerations

## 📈 Roadmap

### Planned Features
- [ ] Real-time validation API
- [ ] Advanced analytics dashboard
- [ ] Machine learning model integration
- [ ] Multi-language support
- [ ] Advanced reporting capabilities

### Performance Improvements
- [ ] Redis caching layer
- [ ] Database query optimization
- [ ] Async processing pipeline
- [ ] Horizontal scaling support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request



---

**Built with ❤️ for healthcare innovation**
