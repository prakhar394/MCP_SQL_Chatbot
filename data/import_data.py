#!/usr/bin/env python3
"""
Script to import CSV data into MySQL database.
This is a more reliable alternative to LOAD DATA INFILE.
"""

import csv
import mysql.connector
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_config():
    """Get database configuration from environment variables."""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", 3306)),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "partselect")
    }

def create_parts_table(cursor):
    """Create the parts table if it doesn't exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            part_name TEXT,
            part_id VARCHAR(255),
            mpn_id VARCHAR(255),
            part_price DECIMAL(10, 2),
            install_difficulty VARCHAR(255),
            install_time VARCHAR(255),
            symptoms TEXT,
            appliance_types TEXT,
            replace_parts TEXT,
            brand VARCHAR(255),
            availability VARCHAR(255),
            install_video_url TEXT,
            product_url TEXT
        )
    """)

def create_repairs_table(cursor):
    """Create the repairs table if it doesn't exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repairs (
            Product VARCHAR(255),
            symptom VARCHAR(255),
            description TEXT,
            percentage INT,
            parts TEXT,
            symptom_detail_url TEXT,
            difficulty VARCHAR(255),
            repair_video_url TEXT
        )
    """)

def import_parts_csv(cursor, csv_file):
    """Import parts data from CSV file."""
    print(f"Importing parts from {csv_file}...")
    
    # Clear existing data (optional - comment out if you want to keep existing data)
    cursor.execute("TRUNCATE TABLE parts")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        insert_query = """
            INSERT INTO parts (part_name, part_id, mpn_id, part_price, install_difficulty, 
                             install_time, symptoms, appliance_types, replace_parts, brand, 
                             availability, install_video_url, product_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        rows = []
        for row in reader:
            # Convert empty strings to None for NULL values
            part_price = None
            if row['part_price'] and row['part_price'].strip():
                try:
                    part_price = float(row['part_price'])
                except ValueError:
                    part_price = None
            
            rows.append((
                row['part_name'] or None,
                row['part_id'] or None,
                row['mpn_id'] or None,
                part_price,
                row['install_difficulty'] or None,
                row['install_time'] or None,
                row['symptoms'] or None,
                row['appliance_types'] or None,
                row['replace_parts'] or None,
                row['brand'] or None,
                row['availability'] or None,
                row['install_video_url'] or None,
                row['product_url'] or None
            ))
        
        cursor.executemany(insert_query, rows)
        print(f"Imported {len(rows)} parts records")

def import_repairs_csv(cursor, csv_file):
    """Import repairs data from CSV file."""
    print(f"Importing repairs from {csv_file}...")
    
    # Clear existing data (optional - comment out if you want to keep existing data)
    cursor.execute("TRUNCATE TABLE repairs")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        insert_query = """
            INSERT INTO repairs (Product, symptom, description, percentage, parts, 
                               symptom_detail_url, difficulty, repair_video_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        rows = []
        for row in reader:
            # Convert percentage to int or None
            percentage = None
            if row['percentage'] and row['percentage'].strip():
                try:
                    percentage = int(row['percentage'])
                except ValueError:
                    percentage = None
            
            rows.append((
                row['Product'] or None,
                row['symptom'] or None,
                row['description'] or None,
                percentage,
                row['parts'] or None,
                row['symptom_detail_url'] or None,
                row['difficulty'] or None,
                row['repair_video_url'] or None
            ))
        
        cursor.executemany(insert_query, rows)
        print(f"Imported {len(rows)} repairs records")

def main():
    # Get script directory
    script_dir = Path(__file__).parent
    
    # Get database configuration
    config = get_db_config()
    
    # Prompt for password if not in environment
    if not config['password']:
        config['password'] = input("Enter MySQL password: ")
    
    try:
        # Connect to database
        print(f"Connecting to MySQL database {config['database']}...")
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        # Create tables
        print("Creating tables...")
        create_parts_table(cursor)
        create_repairs_table(cursor)
        conn.commit()
        
        # Import CSV files
        parts_file = script_dir / 'all_parts.csv'
        repairs_file = script_dir / 'all_repairs.csv'
        
        if parts_file.exists():
            import_parts_csv(cursor, parts_file)
            conn.commit()
        else:
            print(f"Warning: {parts_file} not found")
        
        if repairs_file.exists():
            import_repairs_csv(cursor, repairs_file)
            conn.commit()
        else:
            print(f"Warning: {repairs_file} not found")
        
        print("Import completed successfully!")
        
    except mysql.connector.Error as e:
        print(f"MySQL Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()

