#!/usr/bin/env python3
"""
Reset database with updated enum values
"""
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcm_app import create_app
from rcm_app.extensions import db

def main():
    app = create_app()
    
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("Dropped all tables")
        
        # Create all tables with new schema
        db.create_all()
        print("Created all tables with updated schema")

if __name__ == "__main__":
    main()