# RCM AI Agent Backend - Enhanced Implementation

## Overview

This is an enhanced Flask backend for the RCM (Revenue Cycle Management) Validation Engine that incorporates an AI agent framework using ReAct (Reasoning + Acting) approach with Gemini 2.0 Flash. The system processes healthcare claims data against technical and medical adjudication rules using intelligent, autonomous agents.

## Key Features

### 🤖 AI Agent Framework
- **ReAct Agent**: Step-by-step reasoning and action execution
- **LangChain Integration**: Robust agent orchestration
- **Gemini 2.0 Flash**: Advanced reasoning capabilities
- **Tool-based Architecture**: Modular validation tools

### 🔧 Enhanced Validation
- **Static Rule Checking**: Service codes, diagnosis codes, paid amounts, ID formats
- **LLM Queries**: Nuanced error explanations and recommendations
- **Database Queries**: Historical context and similar claims analysis
- **External API Calls**: Mock approval verification and member/facility validation

### 📊 Complete Data Management
- **Master Table**: All required fields with proper status mapping
- **Refined Table**: Cleaned and normalized data
- **Metrics Table**: Aggregated statistics for charts
- **Audit Table**: Comprehensive logging of agent actions

### 🚀 API Endpoints
- **POST /upload**: CSV file upload with AI agent validation
- **POST /validate**: Specific claim validation using AI agent
- **GET /results**: Complete results with pagination and chart data
- **GET /audit**: Agent action logs with filtering
- **POST /agent**: Direct agent querying for analysis
- **GET /health**: System health check

## Architecture

```
rcm_app/
├── agent/                    # AI Agent Framework
│   ├── react_agent.py       # Main ReAct agent implementation
│   └── tools/               # Agent tools
│       ├── validation_tools.py    # Main validation orchestrator
│       ├── static_rules.py        # Static business rules
│       ├── llm_queries.py         # LLM query tool
│       ├── database_queries.py    # Database context tool
│       └── external_api.py        # External API mock tool
├── api/                     # API Endpoints
│   └── claims.py           # Enhanced claims API
├── models/                  # Database Models
│   └── models.py           # Updated with Audit table
├── pipeline/               # Processing Engines
│   ├── engine.py          # Original linear engine
│   └── agent_engine.py    # AI agent-driven engine
├── rules/                  # Rule Management
│   └── loader.py          # Tenant-specific rule loading
└── utils/                  # Utilities
    ├── llm.py             # Enhanced LLM client
    ├── validators.py      # Static validators
    └── error_handler.py   # Error handling and logging
```

## Installation

### Prerequisites
- Python 3.8+
- PostgreSQL (or SQLite for development)
- Google API Key for Gemini

### Setup

1. **Clone and navigate to the project**:
   ```bash
   cd RCM-backend
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**:
   ```bash
   export GOOGLE_API_KEY="your_gemini_api_key"
   export GEMINI_MODEL="gemini-2.0-flash"
   export DATABASE_URL="postgresql://user:pass@localhost/rcm_db"
   export JWT_SECRET_KEY="your_jwt_secret"
   ```

5. **Initialize database**:
   ```bash
   python init_db.py
   ```

6. **Run the application**:
   ```bash
   python run.py
   ```

## Configuration

### Tenant Configuration
Update `configs/tenant_tenant_demo.json`:
```json
{
  "paid_threshold_aed": 250,
  "id_rules": {
    "uppercase_required": true,
    "patterns": {
      "national_id": "^[A-Z0-9]{5,}$",
      "member_id": "^[A-Z0-9]{5,}$",
      "facility_id": "^[A-Z0-9]{3,}$"
    }
  },
  "services_requiring_approval_file": "services.txt",
  "diagnoses_file": "diagnoses.txt"
}
```

### Rule Files
- `rules/tenant_demo/services.txt`: Service codes requiring approval
- `rules/tenant_demo/diagnoses.txt`: Valid diagnosis codes

## API Usage

### Upload Claims
```bash
curl -X POST http://localhost:5000/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@claims.csv" \
  -F "tenant_id=tenant_demo"
```

### Validate Specific Claims
```bash
curl -X POST http://localhost:5000/validate \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "tenant_demo", "claim_ids": ["claim-1", "claim-2"]}'
```

### Get Results with Pagination
```bash
curl -X GET "http://localhost:5000/results?tenant_id=tenant_demo&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Query AI Agent
```bash
curl -X POST http://localhost:5000/agent \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "tenant_demo", "claim_id": "claim-1", "query": "Explain the validation errors"}'
```

### Get Audit Logs
```bash
curl -X GET "http://localhost:5000/audit?tenant_id=tenant_demo&page=1&page_size=20" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Validation Rules

### Technical Rules
- **ID Formats**: Must be uppercase alphanumeric
- **Unique ID**: Format `first4(national_id)-middle4(member_id)-last4(facility_id)`
- **Service Codes**: SRV1001, SRV1002, SRV2008 require approval
- **Paid Amount**: > AED 250 requires approval
- **Approval Number**: Valid format (e.g., APP001), invalid: NA, "Obtain approval"

### Medical Rules
- **Diagnosis Codes**: E11.9, R07.9, Z34.0 require approval
- **Clinical Validation**: LLM-based nuanced analysis

### Status Mapping
- **Validated**: No errors found
- **Not Validated**: Any error found

### Error Types
- **No error**: All validations pass
- **Technical**: ID format, service code, paid amount issues
- **Medical**: Diagnosis code issues
- **Both**: Combination of technical and medical errors

## AI Agent Features

### ReAct Approach
The agent follows a Reasoning + Acting pattern:
1. **Reason**: Analyze the claim step-by-step
2. **Act**: Use appropriate tools for validation
3. **Observe**: Process tool results
4. **Repeat**: Continue until complete analysis

### Available Tools
1. **Static Rules Tool**: Apply business rules
2. **LLM Query Tool**: Get nuanced explanations
3. **Database Query Tool**: Historical context
4. **External API Tool**: Mock verifications

### Confidence Scoring
- **0.95-1.0**: High confidence (clear rule violations)
- **0.8-0.94**: Medium confidence (some ambiguity)
- **0.5-0.79**: Low confidence (requires review)
- **0.0-0.49**: Very low confidence (manual review needed)

## Testing

### Run Unit Tests
```bash
python -m pytest tests/test_agent_tools.py -v
```

### Run Integration Tests
```bash
python -m pytest tests/test_agent_integration.py -v
```

### Run All Tests
```bash
python -m pytest tests/ -v
```

## Error Handling

The system includes comprehensive error handling:
- **Validation Errors**: Graceful fallback to static validation
- **Agent Errors**: Automatic retry with fallback
- **Database Errors**: Transaction rollback and logging
- **LLM Errors**: Fallback to static explanations

## Monitoring and Logging

### Audit Trail
All agent actions are logged in the Audit table:
- Validation start/completion
- Tool usage and results
- Error occurrences
- Performance metrics

### Health Monitoring
- **GET /health**: System status check
- **Database connectivity**: Automatic health checks
- **LLM availability**: API key validation

## Performance Considerations

### Scalability
- **Batch Processing**: Efficient CSV processing
- **Connection Pooling**: Database optimization
- **Caching**: Rule loading optimization
- **Pagination**: Large result set handling

### Resource Management
- **Memory**: Efficient pandas operations
- **API Limits**: LLM rate limiting
- **Database**: Query optimization

## Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "run.py"]
```

### Environment Variables
```bash
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
DATABASE_URL=postgresql://user:pass@localhost/rcm_db
JWT_SECRET_KEY=your_jwt_secret
FLASK_ENV=production
```

## Troubleshooting

### Common Issues

1. **Agent Validation Fails**:
   - Check Google API key
   - Verify LLM model availability
   - Review audit logs for errors

2. **Database Connection Issues**:
   - Verify DATABASE_URL
   - Check PostgreSQL service
   - Review connection pooling

3. **Rule Loading Errors**:
   - Verify tenant configuration files
   - Check file permissions
   - Validate JSON syntax

### Debug Mode
```bash
export FLASK_DEBUG=1
python run.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is part of the HumaEIN case study implementation.

## Support

For issues and questions:
1. Check the audit logs
2. Review error handling logs
3. Consult the API documentation
4. Check system health endpoint