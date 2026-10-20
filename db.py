import json
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from config import DATA_DIR, DB_PATH

@contextmanager
def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def setup_database():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers(
            customer_id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders(
            order_id INTEGER PRIMARY KEY, customer_id TEXT NOT NULL,
            items TEXT NOT NULL, price REAL NOT NULL, status TEXT NOT NULL,
            order_date TEXT NOT NULL, carrier TEXT, delivery_date TEXT,
            notes TEXT DEFAULT '', FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
        );
        CREATE TABLE IF NOT EXISTS tickets(
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT NOT NULL,
            order_id INTEGER, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL, FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
        );
        CREATE TABLE IF NOT EXISTS refunds(
            refund_id INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL UNIQUE,
            customer_id TEXT NOT NULL, order_id INTEGER NOT NULL, amount REAL NOT NULL,
            reason TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pending_approvals(
            approval_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, customer_id TEXT NOT NULL,
            order_id INTEGER NOT NULL, amount REAL NOT NULL, reason TEXT NOT NULL,
            explanation TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            human_note TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        """)
        if conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]:
            return
        customers = [
            ("CUST001","Aarav Sharma","aarav@example.com"),
            ("CUST002","Priya Patil","priya@example.com"),
            ("CUST003","Rohan Deshmukh","rohan@example.com"),
            ("CUST004","Ananya Joshi","ananya@example.com"),
            ("CUST005","Kabir Mehta","kabir@example.com"),
        ]
        conn.executemany("INSERT INTO customers VALUES(?,?,?)", customers)
        products = [
            ("Wireless Mouse",799),("Mechanical Keyboard",2499),("USB-C Hub",1799),
            ("Bluetooth Headphones",3299),("27-inch Monitor",14999),("Laptop",54999),
            ("Webcam",2299),("External SSD",4999)
        ]
        statuses = ["processing","shipped","delivered","delivered","processing","shipped","delivered","processing"]
        today = date.today()
        orders = []
        for i in range(20):
            customer = customers[i % 5][0]
            product, price = products[i % len(products)]
            status = statuses[i % len(statuses)]
            order_date = today - timedelta(days=2 + i * 2)
            delivery = (order_date + timedelta(days=4)).isoformat() if status == "delivered" else None
            orders.append((1042+i, customer, json.dumps([product]), float(price), status,
                           order_date.isoformat(), "BlueDart" if i%2 == 0 else "Delhivery",
                           delivery, ""))
        conn.executemany("""INSERT INTO orders
            (order_id,customer_id,items,price,status,order_date,carrier,delivery_date,notes)
            VALUES(?,?,?,?,?,?,?,?,?)""", orders)

def get_customer_list():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT customer_id,name FROM customers ORDER BY customer_id").fetchall()]

def get_order_for_customer(order_id, customer_id):
    with get_connection() as conn:
        row = conn.execute("""SELECT order_id,customer_id,items,price,status,order_date,
            carrier,delivery_date,notes FROM orders WHERE order_id=? AND customer_id=?""",
            (int(order_id), customer_id)).fetchone()
    if not row: return None
    d = dict(row); d["items"] = json.loads(d["items"]); return d

def list_orders_for_customer(customer_id):
    with get_connection() as conn:
        rows = conn.execute("""SELECT order_id,items,price,status,order_date,carrier,delivery_date
            FROM orders WHERE customer_id=? ORDER BY order_date DESC""", (customer_id,)).fetchall()
    result=[]
    for row in rows:
        d=dict(row); d["items"]=json.loads(d["items"]); result.append(d)
    return result

def create_ticket(customer_id, order_id, reason):
    from datetime import datetime, timezone
    with get_connection() as conn:
        if order_id is not None:
            exists=conn.execute("SELECT 1 FROM orders WHERE order_id=? AND customer_id=?",
                                 (int(order_id),customer_id)).fetchone()
            if not exists: return {"ok":False,"message":"Order not found for logged-in customer."}
        cur=conn.execute("""INSERT INTO tickets(customer_id,order_id,reason,status,created_at)
            VALUES(?,?,?,'open',?)""",
            (customer_id, int(order_id) if order_id is not None else None,
             reason[:1000], datetime.now(timezone.utc).isoformat()))
        return {"ok":True,"ticket_id":cur.lastrowid,"status":"open"}

def create_pending_approval(approval_id, thread_id, customer_id, order_id, amount, reason, explanation):
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""INSERT OR IGNORE INTO pending_approvals
            (approval_id,thread_id,customer_id,order_id,amount,reason,explanation,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,'pending',?,?)""",
            (approval_id,thread_id,customer_id,int(order_id),float(amount),reason,explanation,now,now))

def list_pending_approvals():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("""SELECT * FROM pending_approvals
            WHERE status='pending' ORDER BY created_at""").fetchall()]

def get_approval(approval_id):
    with get_connection() as conn:
        r=conn.execute("SELECT * FROM pending_approvals WHERE approval_id=?",(approval_id,)).fetchone()
        return dict(r) if r else None

def set_approval_status(approval_id, status, note=""):
    from datetime import datetime, timezone
    with get_connection() as conn:
        conn.execute("""UPDATE pending_approvals SET status=?,human_note=?,updated_at=?
            WHERE approval_id=? AND status='pending'""",
            (status,note[:1000],datetime.now(timezone.utc).isoformat(),approval_id))

def issue_refund_idempotent(customer_id, order_id, amount, reason, idempotency_key):
    """Record one refund at most once. This demo records, but does not move real money."""
    from datetime import datetime, timezone
    with get_connection() as conn:
        order=conn.execute("SELECT price FROM orders WHERE order_id=? AND customer_id=?",
                           (int(order_id),customer_id)).fetchone()
        if not order: return {"ok":False,"message":"Order not found for logged-in customer."}
        if amount <= 0 or amount > float(order["price"]):
            return {"ok":False,"message":"Refund amount is outside the verified order amount."}
        conn.execute("""INSERT OR IGNORE INTO refunds
            (idempotency_key,customer_id,order_id,amount,reason,status,created_at)
            VALUES(?,?,?,?,?,'recorded',?)""",
            (idempotency_key,customer_id,int(order_id),float(amount),reason,
             datetime.now(timezone.utc).isoformat()))
        row=conn.execute("SELECT refund_id,amount,status FROM refunds WHERE idempotency_key=?",
                         (idempotency_key,)).fetchone()
        return {"ok":True,"refund_id":row["refund_id"],"amount":row["amount"],"status":row["status"]}
