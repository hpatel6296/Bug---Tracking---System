import os
import sqlite3

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
CORS(app)

DATABASE_PATH = os.path.join(app.root_path, 'bug_tracker.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def initialize_database():
    conn = get_db_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            role TEXT NOT NULL DEFAULT 'Developer'
                CHECK (role IN ('Developer', 'Tester', 'Project Manager')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS bug_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT DEFAULT 'Medium'
                CHECK (priority IN ('Critical', 'High', 'Medium', 'Low')),
            status TEXT DEFAULT 'Open'
                CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
            reporter_id INTEGER NOT NULL,
            assignee_id INTEGER,
            environment TEXT,
            url_route TEXT,
            error_log TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE RESTRICT,
            FOREIGN KEY (assignee_id) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bug_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (bug_id) REFERENCES bug_records(id) ON DELETE CASCADE
        );
    ''')
    cursor = conn.cursor()
    seeded_users = [
        ('alice_dev', 'alice@company.com', 'alice123', 'Developer'),
        ('bob_tester', 'bob@company.com', 'bob123', 'Tester'),
        ('charlie_pm', 'charlie@company.com', 'charlie123', 'Project Manager'),
        ('diana_dev', 'diana@company.com', 'diana123', 'Developer'),
    ]
    for username, email, password, role in seeded_users:
        cursor.execute(
            '''INSERT OR IGNORE INTO users (username, email, password_hash, role)
               VALUES (?, ?, ?, ?)''',
            (username, email, generate_password_hash(password), role)
        )
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE username = ? AND password_hash LIKE 'hashed_pwd_%'",
        (generate_password_hash('alice123'), 'alice_dev')
    )
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE username = ? AND password_hash LIKE 'hashed_pwd_%'",
        (generate_password_hash('bob123'), 'bob_tester')
    )
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE username = ? AND password_hash LIKE 'hashed_pwd_%'",
        (generate_password_hash('charlie123'), 'charlie_pm')
    )
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE username = ? AND password_hash LIKE 'hashed_pwd_%'",
        (generate_password_hash('diana123'), 'diana_dev')
    )
    conn.commit()
    conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    password = data.get('password', '')

    if not user_id or not password:
        return jsonify({"status": "error", "message": "User ID and password are required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, role, password_hash FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({"status": "error", "message": "Invalid user ID or password"}), 401

        return jsonify({
            "status": "success",
            "user": {"id": user['id'], "username": user['username'], "role": user['role']}
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def get_current_user(cursor):
    user_id = request.headers.get('X-User-ID', type=int)
    if not user_id:
        return None

    cursor.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()

@app.route('/')
def serve_frontend():
    return send_from_directory(app.root_path, 'index.html')

@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users ORDER BY id")
        users = [dict(user) for user in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "data": users}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# - READ (GET) - Fetch all bugs with optional filters

@app.route('/api/bugs', methods=['GET'])
def get_bugs():
    status = request.args.get('status')
    priority = request.args.get('priority')
    search = request.args.get('search')

    query = """
        SELECT 
            b.id, b.title, b.description, b.priority, b.status, 
            b.environment, b.url_route, b.error_log, b.created_at, b.updated_at,
            b.reporter_id, b.assignee_id,
            r.username AS reporter_name,
            a.username AS assignee_name
        FROM bug_records b
        JOIN users r ON b.reporter_id = r.id
        LEFT JOIN users a ON b.assignee_id = a.id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND b.status = ?"
        params.append(status)

    if priority:
        query += " AND b.priority = ?"
        params.append(priority)

    if search:
        query += " AND (b.title LIKE ? OR b.description LIKE ? OR b.url_route LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    query += " ORDER BY b.created_at DESC"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        bugs = [dict(bug) for bug in cursor.fetchall()]
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "count": len(bugs), "data": bugs}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# - CREATE (POST) - Report a new bug

@app.route('/api/bugs', methods=['POST'])
def create_bug():
    data = request.get_json()
    title = data.get('title')
    description = data.get('description')
    reporter_id = data.get('reporter_id')
    priority = data.get('priority', 'Medium')
    status = data.get('status', 'Open')
    url_route = data.get('url_route')

    if not title or not description:
        return jsonify({"status": "error", "message": "title, description, and reporter_id are required"}), 400

    query = """
        INSERT INTO bug_records (title, description, priority, status, reporter_id, url_route)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_user = get_current_user(cursor)
        if not current_user:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "A valid user is required"}), 401
        if current_user['role'] == 'Developer':
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Developers cannot create new bugs"}), 403

        reporter_id = current_user['id']
        if not reporter_id:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "A valid reporter is required"}), 400

        cursor.execute(query, (title, description, priority, status, reporter_id, url_route))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Bug reported successfully", "bug_id": new_id}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# - UPDATE (PUT / PATCH) - Full or partial update of bug details

@app.route('/api/bugs/<int:bug_id>', methods=['PUT', 'PATCH'])
def update_bug(bug_id):
    data = request.get_json()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_user = get_current_user(cursor)
        if not current_user:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "A valid user is required"}), 401
        cursor.execute("SELECT title, status, reporter_id, assignee_id FROM bug_records WHERE id = ?", (bug_id,))
        bug = cursor.fetchone()

        if not bug:
            return jsonify({"status": "error", "message": "Bug not found"}), 404

        title = data.get('title')
        description = data.get('description')
        priority = data.get('priority')
        new_status = data.get('status')
        new_assignee_id = data.get('assignee_id')
        url_route = data.get('url_route')

        updates = []
        params = []

        if current_user['role'] == 'Tester' and new_status and new_status != bug['status']:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Testers cannot change bug status"}), 403

        if title: updates.append("title = ?"); params.append(title)
        if description: updates.append("description = ?"); params.append(description)
        if priority: updates.append("priority = ?"); params.append(priority)
        if new_status: updates.append("status = ?"); params.append(new_status)
        if new_assignee_id is not None: updates.append("assignee_id = ?"); params.append(new_assignee_id)
        if url_route is not None: updates.append("url_route = ?"); params.append(url_route)

        if not updates:
            return jsonify({"status": "error", "message": "No fields provided to update"}), 400

        params.append(bug_id)
        update_query = f"UPDATE bug_records SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(update_query, tuple(params))

        # Log notification on status change
        if new_status and new_status != bug['status']:
            msg = f"Bug #{bug_id} status updated to '{new_status}'"
            if bug['reporter_id']:
                cursor.execute("INSERT INTO notifications (user_id, bug_id, message) VALUES (?, ?, ?)", 
                               (bug['reporter_id'], bug_id, msg))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": f"Bug #{bug_id} updated successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# - DELETE (DELETE) - Remove a bug record

@app.route('/api/bugs/<int:bug_id>', methods=['DELETE'])
def delete_bug(bug_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_user = get_current_user(cursor)
        if not current_user:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "A valid user is required"}), 401
        if current_user['role'] != 'Project Manager':
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Only Project Managers can delete bugs"}), 403

        cursor.execute("DELETE FROM bug_records WHERE id = ?", (bug_id,))
        conn.commit()
        affected_rows = cursor.rowcount
        cursor.close()
        conn.close()

        if affected_rows == 0:
            return jsonify({"status": "error", "message": "Bug not found"}), 404

        return jsonify({"status": "success", "message": f"Bug #{bug_id} deleted successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# - NOTIFICATIONS ENDPOINTS

@app.route('/api/notifications/<int:user_id>', methods=['GET'])
def get_notifications(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, bug_id, message, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 15", (user_id,))
        notifs = [dict(notif) for notif in cursor.fetchall()]
        unread_count = sum(1 for n in notifs if not n['is_read'])
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "unread_count": unread_count, "data": notifs}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/notifications/read/<int:notif_id>', methods=['PATCH'])
def mark_notification_read(notif_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = TRUE WHERE id = ?", (notif_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "Notification marked as read"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True, port=5000)