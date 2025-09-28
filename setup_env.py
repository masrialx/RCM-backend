#!/usr/bin/env python3
"""
Environment setup script for RCM Backend
This script helps set up the environment variables and database for the RCM backend.
"""

import os
import sys
from pathlib import Path

def setup_environment():
    """Set up environment variables and database"""
    
    # Get the project root directory
    project_root = Path(__file__).parent
    
    # Set default environment variables
    env_vars = {
        "FLASK_APP": "run.py",
        "FLASK_ENV": "development",
        "FLASK_DEBUG": "1",
        "HOST": "0.0.0.0",
        "PORT": "8000",
        "JWT_SECRET_KEY": "your-secret-key-change-in-production",
        "JWT_ACCESS_MINUTES": "720",
        "DEFAULT_TENANT_ID": "tenant_demo",
        "MAX_UPLOAD_SIZE_MB": "25",
        "DATABASE_URL": f"sqlite:///{project_root}/instance/rcm.db"
    }
    
    # Create .env file if it doesn't exist
    env_file = project_root / ".env"
    if not env_file.exists():
        print("Creating .env file...")
        with open(env_file, 'w') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
        print(f"Created .env file at {env_file}")
    else:
        print(".env file already exists")
    
    # Create instance directory if it doesn't exist
    instance_dir = project_root / "instance"
    instance_dir.mkdir(exist_ok=True)
    print(f"Instance directory: {instance_dir}")
    
    # Initialize database
    print("Initializing database...")
    try:
        from rcm_app import create_app
        from rcm_app.extensions import db
        
        app = create_app()
        with app.app_context():
            db.create_all()
            print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False
    
    print("\nEnvironment setup complete!")
    print("\nTo run the backend:")
    print("1. Activate virtual environment: source venv/bin/activate")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Run the server: python run.py")
    print("\nThe server will be available at: http://localhost:8000")
    
    return True

if __name__ == "__main__":
    success = setup_environment()
    sys.exit(0 if success else 1)