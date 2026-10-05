import sqlite3
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
DB_NAME = "events.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # 1. Events Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL
        )
    """)
    # 2. Registrations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            user_email TEXT NOT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    """)
    # Add initial sample events if empty
    cursor.execute("SELECT COUNT(*) FROM events")
    if cursor.fetchone()[0] == 0:
        sample_events = [
            ("Tech Conference 2026", "Annual technology and developer summit", "2026-11-15", "Bangalore", 100),
            ("Python & Flask Bootcamp", "Hands-on session on backend API development", "2026-12-05", "Online", 50)
        ]
        cursor.executemany("INSERT INTO events (title, description, date, location, capacity) VALUES (?, ?, ?, ?, ?)", sample_events)
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

@app.route('/')
def home():
    return render_template('index.html')

# API 1: List all events
@app.route('/api/events', methods=['GET'])
def get_events():
    events = query_db("SELECT * FROM events")
    return jsonify([dict(e) for e in events]), 200

# API 2: Event details & remaining seats
@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    event = query_db("SELECT * FROM events WHERE id = ?", (event_id,), one=True)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    
    count = query_db("SELECT COUNT(*) as count FROM registrations WHERE event_id = ?", (event_id,), one=True)
    remaining_seats = event['capacity'] - count['count']
    res = dict(event)
    res['remaining_seats'] = remaining_seats
    return jsonify(res), 200

# API 3: Submit registration
@app.route('/api/events/<int:event_id>/register', methods=['POST'])
def register_event(event_id):
    data = request.get_json(silent=True) or request.form
    name = data.get('user_name')
    email = data.get('user_email')

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    event = query_db("SELECT * FROM events WHERE id = ?", (event_id,), one=True)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    count = query_db("SELECT COUNT(*) as count FROM registrations WHERE event_id = ?", (event_id,), one=True)
    if count['count'] >= event['capacity']:
        return jsonify({"error": "Event is fully booked"}), 400

    existing = query_db("SELECT id FROM registrations WHERE event_id = ? AND user_email = ?", (event_id, email), one=True)
    if existing:
        return jsonify({"error": "This email is already registered for this event"}), 400

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO registrations (event_id, user_name, user_email) VALUES (?, ?, ?)", (event_id, name, email))
    reg_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"message": "Registration successful!", "registration_id": reg_id}), 201

# API 4: View user registrations by email
@app.route('/api/registrations', methods=['GET'])
def get_user_registrations():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Email query parameter is required"}), 400

    regs = query_db("""
        SELECT r.id as registration_id, r.user_name, r.user_email, e.title, e.date, e.location 
        FROM registrations r 
        JOIN events e ON r.event_id = e.id 
        WHERE r.user_email = ?
    """, (email,))
    return jsonify([dict(r) for r in regs]), 200

# API 5: Cancel registration
@app.route('/api/registrations/<int:reg_id>', methods=['DELETE'])
def cancel_registration(reg_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        return jsonify({"error": "Registration not found"}), 404
    return jsonify({"message": "Registration cancelled successfully"}), 200

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)