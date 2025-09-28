import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    database_url: str
    jwt_secret_key: str
    jwt_access_minutes: int
    google_api_key: Optional[str]
    default_tenant_id: str
    max_upload_mb: int

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @staticmethod
    def from_env() -> "AppConfig":
        # Build an absolute default path to instance/rcm.db next to this package
        pkg_root = Path(__file__).resolve().parent.parent
        default_sqlite_path = pkg_root / "instance" / "rcm.db"
        default_sqlite_url = f"sqlite:///{default_sqlite_path}"
        return AppConfig(
            database_url=os.getenv("DATABASE_URL", default_sqlite_url),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me"),
            jwt_access_minutes=int(os.getenv("JWT_ACCESS_MINUTES", "720")),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            default_tenant_id=os.getenv("DEFAULT_TENANT_ID", "tenant_demo"),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "25")),
        )
