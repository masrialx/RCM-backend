from datetime import datetime
from sqlalchemy import Enum as SAEnum
from ..extensions import db
from sqlalchemy.types import JSON


ErrorTypeEnum = SAEnum("Technical", "Medical", "Both", "None", name="error_type_enum")


class Master(db.Model):
    __tablename__ = "claims_master"
    __table_args__ = {"sqlite_autoincrement": True}
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(db.String(64), unique=True, nullable=False)
    encounter_type = db.Column(db.String(64))
    service_date = db.Column(db.Date)
    national_id = db.Column(db.String(64))
    member_id = db.Column(db.String(64))
    facility_id = db.Column(db.String(64))
    unique_id = db.Column(db.String(128))
    diagnosis_codes = db.Column(JSON, nullable=True)
    service_code = db.Column(db.String(64))
    paid_amount_aed = db.Column(db.Numeric(14, 2))
    approval_number = db.Column(db.String(64))
    status = db.Column(db.String(32), default="pending")
    error_type = db.Column(ErrorTypeEnum, default="None", nullable=False)
    error_explanation = db.Column(JSON)
    recommended_action = db.Column(JSON)
    tenant_id = db.Column(db.String(64), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Refined(db.Model):
    __tablename__ = "claims_refined"
    __table_args__ = {"sqlite_autoincrement": True}
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(db.String(64), db.ForeignKey("claims_master.claim_id"), nullable=False)
    normalized_national_id = db.Column(db.String(64))
    normalized_member_id = db.Column(db.String(64))
    normalized_facility_id = db.Column(db.String(64))
    final_action = db.Column(db.String(32))  # accept/reject/escalate
    status = db.Column(db.String(32))
    error_type = db.Column(ErrorTypeEnum, default="None", nullable=False)
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

