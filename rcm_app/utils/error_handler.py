"""
Comprehensive error handling and logging utilities
"""

import traceback
from typing import Dict, Any, Optional
from flask import current_app, request
from datetime import datetime
from ..extensions import db
from ..models.models import Audit


class ErrorHandler:
    """Centralized error handling and logging"""
    
    @staticmethod
    def log_error(error: Exception, context: Dict[str, Any] = None, tenant_id: str = None) -> None:
        """Log error with context to audit table and Flask logger"""
        try:
            error_details = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc(),
                "context": context or {},
                "request_data": {
                    "method": request.method if request else None,
                    "url": request.url if request else None,
                    "headers": dict(request.headers) if request else None
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Log to Flask logger
            current_app.logger.error(f"Error occurred: {error_details}")
            
            # Log to audit table if tenant_id provided
            if tenant_id:
                try:
                    audit = Audit(
                        claim_id="SYSTEM_ERROR",
                        action="error_occurred",
                        outcome="error",
                        details=error_details,
                        tenant_id=tenant_id
                    )
                    db.session.add(audit)
                    db.session.commit()
                except Exception as audit_error:
                    current_app.logger.error(f"Failed to log error to audit: {audit_error}")
                    
        except Exception as log_error:
            print(f"Failed to log error: {log_error}")
    
    @staticmethod
    def handle_validation_error(error: Exception, claim_id: str = None, tenant_id: str = None) -> Dict[str, Any]:
        """Handle validation-specific errors"""
        context = {
            "claim_id": claim_id,
            "error_type": "validation_error",
            "component": "validation_engine"
        }
        
        ErrorHandler.log_error(error, context, tenant_id)
        
        return {
            "error": "Validation failed",
            "message": str(error),
            "claim_id": claim_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def handle_agent_error(error: Exception, claim_id: str = None, tenant_id: str = None) -> Dict[str, Any]:
        """Handle AI agent-specific errors"""
        context = {
            "claim_id": claim_id,
            "error_type": "agent_error",
            "component": "ai_agent"
        }
        
        ErrorHandler.log_error(error, context, tenant_id)
        
        return {
            "error": "AI Agent failed",
            "message": str(error),
            "claim_id": claim_id,
            "timestamp": datetime.utcnow().isoformat(),
            "fallback_available": True
        }
    
    @staticmethod
    def handle_database_error(error: Exception, operation: str = None, tenant_id: str = None) -> Dict[str, Any]:
        """Handle database-specific errors"""
        context = {
            "operation": operation,
            "error_type": "database_error",
            "component": "database"
        }
        
        ErrorHandler.log_error(error, context, tenant_id)
        
        return {
            "error": "Database operation failed",
            "message": str(error),
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def handle_llm_error(error: Exception, query: str = None, tenant_id: str = None) -> Dict[str, Any]:
        """Handle LLM-specific errors"""
        context = {
            "query": query,
            "error_type": "llm_error",
            "component": "llm_client"
        }
        
        ErrorHandler.log_error(error, context, tenant_id)
        
        return {
            "error": "LLM query failed",
            "message": str(error),
            "query": query,
            "timestamp": datetime.utcnow().isoformat(),
            "fallback_available": True
        }
    
    @staticmethod
    def create_error_response(error: Exception, status_code: int = 500, context: Dict[str, Any] = None) -> tuple:
        """Create standardized error response"""
        error_id = f"ERR_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        response = {
            "error": True,
            "error_id": error_id,
            "message": str(error),
            "type": type(error).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if context:
            response["context"] = context
        
        # Log the error
        ErrorHandler.log_error(error, context)
        
        return response, status_code


class ValidationError(Exception):
    """Custom validation error"""
    pass


class AgentError(Exception):
    """Custom agent error"""
    pass


class DatabaseError(Exception):
    """Custom database error"""
    pass


class LLMError(Exception):
    """Custom LLM error"""
    pass