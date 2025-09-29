from datetime import datetime
from sqlalchemy import Enum as SAEnum
from ..extensions import db
from sqlalchemy.types import JSON


ErrorTypeEnum = SAEnum("Technical error", "Medical error", "Administrative", "Both", "No error", name="error_type_enum")
StatusEnum = SAEnum("Validated", "Not Validated", "pending", name="status_enum")


class Master(db.Model):
    __tablename__ = "claims_master"
    __table_args__ = {"sqlite_autoincrement": True}
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(db.String(64), unique=True, nullable=False)  # Primary identifier
    encounter_type = db.Column(db.String(64))
    service_date = db.Column(db.Date)
    national_id = db.Column(db.String(64))
    member_id = db.Column(db.String(64))
    facility_id = db.Column(db.String(64))
    # unique_id is now a computed property based on claim_id - they are the same identifier
    diagnosis_codes = db.Column(JSON, nullable=True)
    service_code = db.Column(db.String(64))
    paid_amount_aed = db.Column(db.Numeric(14, 2))
    approval_number = db.Column(db.String(64))
    status = db.Column(StatusEnum, default="pending", nullable=False)
    error_type = db.Column(ErrorTypeEnum, default="No error", nullable=False)
    error_explanation = db.Column(JSON)
    recommended_action = db.Column(JSON)
    tenant_id = db.Column(db.String(64), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    @property
    def unique_id(self) -> str:
        """unique_id is always the same as claim_id - they are the same identifier"""
        return self.claim_id
    
    @unique_id.setter
    def unique_id(self, value: str):
        """Setting unique_id also sets claim_id - they are the same identifier"""
        self.claim_id = value


class Refined(db.Model):
    __tablename__ = "claims_refined"
    __table_args__ = {"sqlite_autoincrement": True}
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(db.String(64), db.ForeignKey("claims_master.claim_id"), nullable=False)
    normalized_national_id = db.Column(db.String(64))
    normalized_member_id = db.Column(db.String(64))
    normalized_facility_id = db.Column(db.String(64))
    final_action = db.Column(db.String(32))  # accept/reject/escalate
    status = db.Column(StatusEnum, default="pending", nullable=False)
    error_type = db.Column(ErrorTypeEnum, default="No error", nullable=False)
    tenant_id = db.Column(db.String(64), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Metrics(db.Model):
    __tablename__ = "claims_metrics"
    __table_args__ = {"sqlite_autoincrement": True}
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tenant_id = db.Column(db.String(64), index=True, nullable=False)
    error_category = db.Column(ErrorTypeEnum, nullable=False)
    claim_count = db.Column(db.Integer, default=0, nullable=False)
    paid_sum = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    time_bucket = db.Column(db.Date, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Audit(db.Model):
    __tablename__ = "claims_audit"
    __table_args__ = {"sqlite_autoincrement": True}
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(db.String(64), db.ForeignKey("claims_master.claim_id"), nullable=False)
    action = db.Column(db.String(128), nullable=False)  # e.g., "validation_started", "tool_used", "validation_completed"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    outcome = db.Column(db.String(256))  # e.g., "success", "error", "tool_result"
    details = db.Column(JSON)  # Additional context data
    tenant_id = db.Column(db.String(64), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

