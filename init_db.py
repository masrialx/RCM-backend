#!/usr/bin/env python3
"""Database initialization script to create tables manually."""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from rcm_app import create_app
from rcm_app.extensions import db

def init_database():
    """Initialize the database with all tables."""
    app = create_app()
    
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # Verify tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📋 Created tables: {tables}")
            
            # Test a simple query
            from rcm_app.models.models import Master
            count = Master.query.count()
            print(f"📊 Master table has {count} records")
            
        except Exception as e:
            print(f"❌ Error creating database: {e}")
            return False
    
    return True

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)