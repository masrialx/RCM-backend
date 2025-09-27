"""
External API tool for mock verification calls
"""

from typing import Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import re
import time
import random


class ExternalAPIInput(BaseModel):
    """Input for external API call"""
    approval_number: str = Field(description="Approval number to verify")
    api_type: str = Field(description="Type of API call: approval_verification, member_verification, facility_verification")


class ExternalAPITool(BaseTool):
    """Tool for mock external API calls"""
    
    name: str = "call_external_api"
    description: str = "Make mock external API calls for verification (approval, member, facility)"
    args_schema: type = ExternalAPIInput
    
    def _run(self, approval_number: str, api_type: str) -> str:
        """Make mock external API call"""
        try:
            if api_type == "approval_verification":
                return self._verify_approval(approval_number)
            elif api_type == "member_verification":
                return self._verify_member(approval_number)
            elif api_type == "facility_verification":
                return self._verify_facility(approval_number)
            else:
                return f"Unknown API type: {api_type}"
                
        except Exception as e:
            return f"External API error: {str(e)}"
    
    def _verify_approval(self, approval_number: str) -> str:
        """Mock approval verification API"""
        # Simulate API delay
        time.sleep(0.1)
        
        if not approval_number or approval_number in ["NA", "Obtain approval", ""]:
            return "API Response: Approval verification failed - No approval number provided"
        
        # Mock validation logic
        if self._is_valid_approval_format(approval_number):
            # Simulate random success/failure for realistic testing
            if random.random() > 0.1:  # 90% success rate
                return f"API Response: Approval {approval_number} verified successfully"
            else:
                return f"API Response: Approval {approval_number} verification failed - Not found in system"
        else:
            return f"API Response: Approval {approval_number} verification failed - Invalid format"
    
    def _verify_member(self, member_id: str) -> str:
        """Mock member verification API"""
        time.sleep(0.1)
        
        if not member_id:
            return "API Response: Member verification failed - No member ID provided"
        
        # Mock validation
        if len(member_id) >= 5 and member_id.isalnum():
            return f"API Response: Member {member_id} verified successfully"
        else:
            return f"API Response: Member {member_id} verification failed - Invalid format"
    
    def _verify_facility(self, facility_id: str) -> str:
        """Mock facility verification API"""
        time.sleep(0.1)
        
        if not facility_id:
            return "API Response: Facility verification failed - No facility ID provided"
        
        # Mock validation
        if len(facility_id) >= 3 and facility_id.isalnum():
            return f"API Response: Facility {facility_id} verified successfully"
        else:
            return f"API Response: Facility {facility_id} verification failed - Invalid format"
    
    def _is_valid_approval_format(self, approval_number: str) -> bool:
        """Check if approval number follows valid format"""
        if not approval_number:
            return False
        # Valid format: starts with letters, followed by numbers
        pattern = re.compile(r'^[A-Z]{2,}[0-9]{3,}$')
        return bool(pattern.match(approval_number.upper()))