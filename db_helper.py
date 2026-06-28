import sqlite3
import json
from config import DB_PATH

def get_connection(email, provider='antigravity'):
    """Retrieve connection details from the database by email."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, provider, name, email, isActive, data FROM providerConnections WHERE email = ? AND provider = ?",
            (email, provider)
        )
        row = cursor.fetchone()
        if row:
            try:
                parsed_data = json.loads(row[5])
            except:
                parsed_data = {}
            return {
                "id": row[0],
                "provider": row[1],
                "name": row[2],
                "email": row[3],
                "isActive": bool(row[4]),
                "data": parsed_data
            }
        return None
    finally:
        conn.close()

def delete_connection(email, provider='antigravity'):
    """Delete a connection directly from the database by email to allow a clean retry/reconnect."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM providerConnections WHERE email = ? AND provider = ?",
            (email, provider)
        )
        conn.commit()
        print(f"[DB] Deleted connection for {email} ({provider}) from SQLite database.")
    except Exception as e:
        print(f"[DB] Error deleting connection for {email} ({provider}): {e}")
    finally:
        conn.close()

def is_connection_active(email, provider='antigravity'):
    """Check if the connection for this email is currently active in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT data FROM providerConnections WHERE email = ? AND provider = ?",
            (email, provider)
        )
        row = cursor.fetchone()
        if row:
            try:
                parsed_data = json.loads(row[0])
                return parsed_data.get("testStatus") == "active"
            except:
                pass
        return False
    finally:
        conn.close()
