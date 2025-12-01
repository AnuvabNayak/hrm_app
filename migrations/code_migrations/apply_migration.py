"""
Apply Password Reset Migration
Safely creates password_reset_tokens table
"""

import sqlite3
import os
from datetime import datetime

# Configuration
DATABASE_FILE = "hrm_database.db"
MIGRATION_FILE = "migration_password_reset.sql"

def apply_migration():
    """Apply the password reset table migration."""
    
    print("=" * 60)
    print("PASSWORD RESET TABLE MIGRATION")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if database exists
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ ERROR: Database file '{DATABASE_FILE}' not found!")
        print("   Make sure you're in the hrm_project directory")
        return False
    
    print(f"✅ Database file found: {DATABASE_FILE}")
    
    # Check if migration file exists
    if not os.path.exists(MIGRATION_FILE):
        print(f"❌ ERROR: Migration file '{MIGRATION_FILE}' not found!")
        print("   Make sure you created the migration_password_reset.sql file")
        return False
    
    print(f"✅ Migration file found: {MIGRATION_FILE}")
    print()
    
    # Read migration SQL
    with open(MIGRATION_FILE, 'r', encoding='utf-8') as f:
        migration_sql = f.read()
    
    print("📄 Migration SQL loaded")
    print()
    
    # Connect to database
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        print("✅ Connected to database")
        
        # Execute migration
        print("⏳ Executing migration...")
        cursor.executescript(migration_sql)
        conn.commit()
        print("✅ Migration executed successfully!")
        print()
        
        # Verify table was created
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='password_reset_tokens'
        """)
        result = cursor.fetchone()
        
        if result:
            print("✅ Table 'password_reset_tokens' created successfully!")
            print()
            
            # Show table structure
            cursor.execute("PRAGMA table_info(password_reset_tokens)")
            columns = cursor.fetchall()
            
            print("📊 Table Structure:")
            print("-" * 60)
            for col in columns:
                col_id, name, col_type, not_null, default, pk = col
                print(f"  {name:20} {col_type:15} {'PK' if pk else ''}")
            print("-" * 60)
            print()
            
            # Show indexes
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='password_reset_tokens'
            """)
            indexes = cursor.fetchall()
            
            if indexes:
                print("🔍 Indexes Created:")
                print("-" * 60)
                for idx in indexes:
                    print(f"  ✓ {idx[0]}")
                print("-" * 60)
                print()
            
            print("🎉 MIGRATION COMPLETE!")
            print()
            print("Next steps:")
            print("  1. Table created successfully ✅")
            print("  2. Indexes created for fast lookups ✅")
            print("  3. Ready to continue to Step 2")
            print()
            return True
        else:
            print("❌ ERROR: Table was not created")
            return False
            
    except sqlite3.Error as e:
        print(f"❌ DATABASE ERROR: {e}")
        return False
    finally:
        if conn:
            conn.close()
            print("✅ Database connection closed")

if __name__ == "__main__":
    success = apply_migration()
    if success:
        print()
        print("=" * 60)
        print("✅ STEP 1 COMPLETE - DATABASE SETUP SUCCESSFUL!")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ STEP 1 FAILED - Please check errors above")
        print("=" * 60)
