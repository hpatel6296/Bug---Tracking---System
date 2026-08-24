from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Harsh*6296',
    'database': 'bug_tracker_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def get_current_user(cursor):
    user_id = request.headers.get('X-User-ID', type=int)
    if not user_id:
        return None

    cursor.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
    return cursor.fetchone()

@app.route('/')
def serve_frontend():
    return send_from_directory(app.root_path, 'index.html')

@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, role FROM users ORDER BY id")
        users = cursor.fetchall()
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
        query += " AND b.status = %s"
        params.append(status)

    if priority:
        query += " AND b.priority = %s"
        params.append(priority)

    if search:
        query += " AND (b.title LIKE %s OR b.description LIKE %s OR b.url_route LIKE %s)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    query += " ORDER BY b.created_at DESC"

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        bugs = cursor.fetchall()
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
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
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
        cursor = conn.cursor(dictionary=True)
        current_user = get_current_user(cursor)
        if not current_user:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "A valid user is required"}), 401
        if current_user['role'] == 'Tester':
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Testers cannot update bugs"}), 403

        cursor.execute("SELECT title, status, reporter_id, assignee_id FROM bug_records WHERE id = %s", (bug_id,))
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

        if title: updates.append("title = %s"); params.append(title)
        if description: updates.append("description = %s"); params.append(description)
        if priority: updates.append("priority = %s"); params.append(priority)
        if new_status: updates.append("status = %s"); params.append(new_status)
        if new_assignee_id is not None: updates.append("assignee_id = %s"); params.append(new_assignee_id)
        if url_route is not None: updates.append("url_route = %s"); params.append(url_route)

        if not updates:
            return jsonify({"status": "error", "message": "No fields provided to update"}), 400

        params.append(bug_id)
        update_query = f"UPDATE bug_records SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(update_query, tuple(params))

        # Log notification on status change
        if new_status and new_status != bug['status']:
            msg = f"Bug #{bug_id} status updated to '{new_status}'"
            if bug['reporter_id']:
                cursor.execute("INSERT INTO notifications (user_id, bug_id, message) VALUES (%s, %s, %s)", 
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
        cursor = conn.cursor(dictionary=True)
        current_user = get_current_user(cursor)
        if not current_user:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "A valid user is required"}), 401
        if current_user['role'] != 'Project Manager':
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Only Project Managers can delete bugs"}), 403

        cursor.execute("DELETE FROM bug_records WHERE id = %s", (bug_id,))
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
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, bug_id, message, is_read, created_at FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 15", (user_id,))
        notifs = cursor.fetchall()
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
        cursor.execute("UPDATE notifications SET is_read = TRUE WHERE id = %s", (notif_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "Notification marked as read"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)