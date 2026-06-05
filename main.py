from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sqlite3

app = FastAPI(title="Mango Order System")

# Enable CORS so your frontend can communicate securely with the backend APIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "mango_business.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Access columns by name like a dictionary
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")  # Optimize for concurrent access
    return conn

# API Endpoint: Look up a customer profile by phone number
@app.get("/api/customer/{phone}")
def get_customer(phone: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Normalize lookup string
    search_phone = phone.strip()
    
    cursor.execute("SELECT id, customer_name, delivery_address FROM customers WHERE phone_number = ?", (search_phone,))
    customer = cursor.fetchone()
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
        cursor.execute("SELECT id, delivery_address FROM customers WHERE phone_number = ?", (phone,))
        existing_customer = cursor.fetchone()
        
        if existing_customer:
            customer_id = existing_customer["id"]
            # Smoother User Journey: Update address details if they changed them
            if existing_customer["delivery_address"] != address:
                cursor.execute("UPDATE customers SET delivery_address = ? WHERE id = ?", (address, customer_id))
        else:
            # Create a brand new customer profile
            cursor.execute(
                "INSERT INTO customers (phone_number, customer_name, delivery_address) VALUES (?, ?, ?)",
                (phone, name, address)
            )
            customer_id = cursor.lastrowid
            
        # Log the mango order record
        cursor.execute(
            "INSERT INTO orders (customer_id, quantity_kg) VALUES (?, ?)",
            (customer_id, quantity)
        )
        
        conn.commit()
        return {"status": "success", "message": f"Order for {quantity}kg recorded successfully!"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# Serve static frontend files (we will create a static folder next)
app.mount("/", StaticFiles(directory="static", html=True), name="static")