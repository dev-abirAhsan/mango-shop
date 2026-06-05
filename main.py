from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Mango Order System")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Render automatically provides DATABASE_URL. If running locally, it defaults to a placeholder.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://your_local_username:your_local_password@localhost:5432/mangoshop")

def get_db_connection():
    # RealDictCursor allows us to fetch records as dictionaries, mimicking SQLite's Row factory
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

# Automatically create tables when the backend app starts up if they do not exist
@app.on_event("startup")
def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create Customers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            phone_number TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            delivery_address TEXT NOT NULL
        );
    """)
    
    # Create index for phone speed queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone_number);")
    
    # 2. Create Orders Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            quantity_kg REAL NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Pending'
        );
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# API Endpoint: Look up a customer profile by phone number
@app.get("/api/customer/{phone}")
def get_customer(phone: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    search_phone = phone.strip()
    
    # PostgreSQL uses standard parameterized (%s) placeholders instead of SQLite's (?)
    cursor.execute("SELECT id, customer_name, delivery_address FROM customers WHERE phone_number = %s", (search_phone,))
    customer = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if customer:
        return {
            "exists": True,
            "id": customer["id"],
            "name": customer["customer_name"],
            "address": customer["delivery_address"]
        }
    return {"exists": False}

# API Endpoint: Handle the order submission workflow
@app.post("/api/order")
def place_order(
    phone: str = Form(...),
    name: str = Form(...),
    address: str = Form(...),
    quantity: float = Form(...)
):
    phone = phone.strip()
    name = name.strip()
    address = address.strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if customer exists
        cursor.execute("SELECT id, delivery_address FROM customers WHERE phone_number = %s", (phone,))
        existing_customer = cursor.fetchone()
        
        if existing_customer:
            customer_id = existing_customer["id"]
            if existing_customer["delivery_address"] != address:
                cursor.execute("UPDATE customers SET delivery_address = %s WHERE id = %s", (address, customer_id))
        else:
            # PostgreSQL uses 'RETURING id' instead of lastrowid to grab auto-increment keys reliably
            cursor.execute(
                "INSERT INTO customers (phone_number, customer_name, delivery_address) VALUES (%s, %s, %s) RETURNING id",
                (phone, name, address)
            )
            customer_id = cursor.fetchone()["id"]
            
        # Log the mango order record
        cursor.execute(
            "INSERT INTO orders (customer_id, quantity_kg) VALUES (%s, %s)",
            (customer_id, quantity)
        )
        
        conn.commit()
        return {"status": "success", "message": f"Order for {quantity}kg recorded successfully!"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Serve static frontend files
app.mount("/", StaticFiles(directory="static", html=True), name="static")