from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_FILE = "finance.db"

# ----------------- Database Helpers -----------------

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # makes rows behave like dict
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            balance REAL DEFAULT 0.00,
            initial_balance REAL DEFAULT 0.00,
            monthly_budget REAL DEFAULT 0.00,
            savings_goal INTEGER DEFAULT 20,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER DEFAULT 1,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            emoji TEXT,
            description TEXT,
            date TEXT,
            original_text TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Categories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            total REAL DEFAULT 0.00,
            count INTEGER DEFAULT 0,
            emoji TEXT,
            UNIQUE(user_id, name)
        )
    """)

    # Goals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY,
            user_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0.00,
            deadline TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Achievements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            achievement_id TEXT NOT NULL,
            unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, achievement_id)
        )
    """)

    # Default user
    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO users (balance, initial_balance, monthly_budget, savings_goal)
            VALUES (0.00, 0.00, 0.00, 20)
        """)

    conn.commit()
    conn.close()
    print("SQLite database initialized successfully!")

# ----------------- API Routes -----------------

@app.route('/api/data', methods=['GET'])
def get_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # User
        cursor.execute("SELECT * FROM users WHERE id = 1")
        user = cursor.fetchone()

        # Transactions
        cursor.execute("""
            SELECT id, type, amount, category, emoji, description, date, original_text
            FROM transactions WHERE user_id = 1
            ORDER BY id DESC
        """)
        transactions = [dict(row) for row in cursor.fetchall()]

        # Categories
        cursor.execute("""
            SELECT name, total, count, emoji
            FROM categories WHERE user_id = 1
        """)
        cats = [dict(row) for row in cursor.fetchall()]
        categories = {c["name"]: {
            "total": c["total"], "count": c["count"], "emoji": c["emoji"]
        } for c in cats}

        # Goals
        cursor.execute("""
            SELECT id, name, target_amount, current_amount, deadline
            FROM goals WHERE user_id = 1
        """)
        goals = []
        for g in cursor.fetchall():
            goals.append({
                "id": g["id"],
                "name": g["name"],
                "targetAmount": g["target_amount"],
                "currentAmount": g["current_amount"],
                "deadline": g["deadline"]
            })

        # Achievements
        cursor.execute("""
            SELECT achievement_id, unlocked_at
            FROM achievements WHERE user_id = 1
        """)
        achievements = []
        for a in cursor.fetchall():
            achievements.append({
                "id": a["achievement_id"],
                "unlockedAt": a["unlocked_at"]
            })

        data = {
            "balance": user["balance"] if user else 0,
            "initialBalance": user["initial_balance"] if user else 0,
            "monthlyBudget": user["monthly_budget"] if user else 0,
            "savingsGoal": user["savings_goal"] if user else 20,
            "transactions": transactions,
            "categories": categories,
            "goals": goals,
            "achievements": achievements
        }

        return jsonify({"success": True, "data": data})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/data', methods=['POST'])
def save_data():
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update user
        cursor.execute("""
            UPDATE users SET
                balance = ?,
                initial_balance = ?,
                monthly_budget = ?,
                savings_goal = ?
            WHERE id = 1
        """, (
            data.get("balance", 0),
            data.get("initialBalance", 0),
            data.get("monthlyBudget", 0),
            data.get("savingsGoal", 20)
        ))

        # Clear and insert transactions
        cursor.execute("DELETE FROM transactions WHERE user_id = 1")
        for t in data.get("transactions", []):
            cursor.execute("""
                INSERT INTO transactions (id, user_id, type, amount, category, emoji, description, date, original_text)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t["id"], t["type"], t["amount"], t["category"],
                t.get("emoji", "💳"), t.get("description", ""),
                t.get("date", ""), t.get("originalText", "")
            ))

        # Clear and insert categories
        cursor.execute("DELETE FROM categories WHERE user_id = 1")
        for name, c in data.get("categories", {}).items():
            cursor.execute("""
                INSERT INTO categories (user_id, name, total, count, emoji)
                VALUES (1, ?, ?, ?, ?)
            """, (
                name, c.get("total", 0), c.get("count", 0), c.get("emoji", "💳")
            ))

        # Clear and insert goals
        cursor.execute("DELETE FROM goals WHERE user_id = 1")
        for g in data.get("goals", []):
            cursor.execute("""
                INSERT INTO goals (id, user_id, name, target_amount, current_amount, deadline)
                VALUES (?, 1, ?, ?, ?, ?)
            """, (
                g["id"], g["name"], g.get("targetAmount", 0),
                g.get("currentAmount", 0), g.get("deadline")
            ))

        # Clear and insert achievements
        cursor.execute("DELETE FROM achievements WHERE user_id = 1")
        for a in data.get("achievements", []):
            cursor.execute("""
                INSERT INTO achievements (user_id, achievement_id, unlocked_at)
                VALUES (1, ?, ?)
            """, (
                a["id"], a.get("unlockedAt")
            ))

        conn.commit()
        return jsonify({"success": True, "message": "Data saved successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/reset', methods=['POST'])
def reset_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM transactions WHERE user_id = 1")
        cursor.execute("DELETE FROM categories WHERE user_id = 1")
        cursor.execute("DELETE FROM goals WHERE user_id = 1")
        cursor.execute("DELETE FROM achievements WHERE user_id = 1")

        cursor.execute("""
            UPDATE users SET
                balance = 0.00,
                initial_balance = 0.00,
                monthly_budget = 0.00,
                savings_goal = 20
            WHERE id = 1
        """)

        conn.commit()
        return jsonify({"success": True, "message": "All data reset successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"success": True, "message": "Server is running"})

# ----------------- Serve Frontend -----------------

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/styles.css')
def serve_css():
    return send_from_directory('.', 'styles.css')

@app.route('/script.js')
def serve_js():
    return send_from_directory('.', 'script.js')


if __name__ == '__main__':
    print("Initializing SQLite database...")
    init_database()
    print("Starting Flask server...")
    app.run(debug=True, port=5000)
