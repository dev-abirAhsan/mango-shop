import sqlite3
import psycopg2
from psycopg2.extras import execute_values

# 1. Connect to your old local SQLite database file
sqlite_conn = sqlite3.connect("mango_business.db")
sqlite_cursor = sqlite_conn.cursor()

# Fetch all existing customers from your SQLite file
sqlite_cursor.execute("SELECT phone_number, customer_name, delivery_address FROM customers;")
local_customers = sqlite_cursor.fetchall()
print(f"📦 Found {len(local_customers)} customers in your local SQLite database.")

if not local_customers:
    print("❌ No local data found to migrate. Exiting.")
    exit()

# 2. Connect to your Live Cloud PostgreSQL database
# PASTE YOUR EXTERNAL DATABASE URL COPIED FROM RENDER BELOW:
POSTGRES_EXTERNAL_URL = "postgresql://mangoshop_user:jQ2kSgY5sJPsXW2GPSvihBwWTPjw0oZY@dpg-d8hgu6urnols73cj4bf0-a.singapore-postgres.render.com/mangoshop"

try:
    pg_conn = psycopg2.connect(POSTGRES_EXTERNAL_URL)
    pg_cursor = pg_conn.cursor()
    
    print("🔄 Migrating profiles to Render Cloud PostgreSQL...")
    
    # Using 'ON CONFLICT DO NOTHING' ensures that running this won't break if a record exists
    insert_query = """
        INSERT INTO customers (phone_number, customer_name, delivery_address) 
        VALUES %s 
        ON CONFLICT (phone_number) DO NOTHING;
    """
    
    # Batch execute the insert to keep it ultra fast
    execute_values(pg_cursor, insert_query, local_customers)
    
    pg_conn.commit()
    print("🚀 Migration completed successfully! Your cloud database is fully synchronized.")
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
finally:
    sqlite_cursor.close()
    sqlite_conn.close()
    if 'pg_cursor' in locals():
        pg_cursor.close()
        pg_conn.close()