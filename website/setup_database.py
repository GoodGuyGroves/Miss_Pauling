#!/usr/bin/env python3
"""
Setup script for creating the SQLite database for the Steam authentication application.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(command):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(command, shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                               universal_newlines=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Error details: {e.stderr}")
        return None

def setup_sqlite(db_path):
    """Setup SQLite database file"""
    db_file = Path(db_path)
    
    # Make sure the directory exists
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    # No need to create the file explicitly, SQLAlchemy will do it
    print(f"SQLite database will be created at: {db_file.absolute()}")
    
    # Update the config file with the database path
    config_path = Path(__file__).parent / "app" / "config.json"
    if config_path.exists():
        import json
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # Update the database path
            if "database" not in config:
                config["database"] = {}
            
            config["database"]["path"] = str(db_file)
            
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
                
            print(f"Updated config file with database path: {db_file}")
        except Exception as e:
            print(f"Error updating config file: {e}")
    
    return True

def run_migrations():
    """Run database migrations using Alembic"""
    print("Running database migrations...")
    result = run_command("alembic upgrade head")
    if result is not None:
        print("Migrations completed successfully.")
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description='Setup SQLite database for Steam authentication app.')
    parser.add_argument('--db-path', default='../db/sqlite.db', help='SQLite database file path')
    parser.add_argument('--skip-migrations', action='store_true', help='Skip running migrations')
    
    args = parser.parse_args()
    
    if not setup_sqlite(args.db_path):
        sys.exit(1)
    
    # Update the config file with the database connection details
    from shared.database import get_database_url
    print(f"Database URL: {get_database_url()}")
    
    if not args.skip_migrations:
        if not run_migrations():
            sys.exit(1)
    
    print("\nDatabase setup completed successfully!")
    print(f"Database: {args.db_path}")
    print("The application is now ready to connect to the database.")

if __name__ == "__main__":
    main()