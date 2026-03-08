from flask import Flask, request, jsonify, send_from_directory
import os
from flask_cors import CORS
import sqlite3
import uuid
from datetime import datetime

app = Flask(__name__)
@app.route('/')
def index():
    return send_from_directory(os.path.dirname(__file__), 'calendar.html')
CORS(app)

DB = 'calendar.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT,
            endTime TEXT,
            location TEXT,
            members TEXT,
            color TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

# GET all events
@app.route('/events', methods=['GET'])
def get_events():
    conn = get_db()
    events = conn.execute('SELECT * FROM events ORDER BY date, time').fetchall()
    conn.close()
    return jsonify([dict(e) for e in events])

# GET single event
@app.route('/events/<id>', methods=['GET'])
def get_event(id):
    conn = get_db()
    event = conn.execute('SELECT * FROM events WHERE id = ?', (id,)).fetchone()
    conn.close()
    if event is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(event))

# POST add event
@app.route('/events', methods=['POST'])
def add_event():
    data = request.json
    if not data or not data.get('name') or not data.get('date'):
        return jsonify({'error': 'name and date are required'}), 400
    event = {
        'id': str(uuid.uuid4()),
        'name': data.get('name'),
        'date': data.get('date'),
        'time': data.get('time', ''),
        'endTime': data.get('endTime', ''),
        'location': data.get('location', ''),
        'members': data.get('members', ''),
        'color': data.get('color', 'sky'),
        'notes': data.get('notes', ''),
    }
    conn = get_db()
    conn.execute('''
        INSERT INTO events (id, name, date, time, endTime, location, members, color, notes)
        VALUES (:id, :name, :date, :time, :endTime, :location, :members, :color, :notes)
    ''', event)
    conn.commit()
    conn.close()
    return jsonify(event), 201

# PUT update event
@app.route('/events/<id>', methods=['PUT'])
def update_event(id):
    data = request.json
    conn = get_db()
    conn.execute('''
        UPDATE events SET name=?, date=?, time=?, endTime=?, location=?, members=?, color=?, notes=?
        WHERE id=?
    ''', (
        data.get('name'), data.get('date'), data.get('time'),
        data.get('endTime'), data.get('location'), data.get('members'),
        data.get('color'), data.get('notes'), id
    ))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# DELETE event
@app.route('/events/<id>', methods=['DELETE'])
def delete_event(id):
    conn = get_db()
    conn.execute('DELETE FROM events WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# Alexa endpoint — parses natural language
@app.route('/alexa', methods=['POST'])
def alexa():
    data = request.json
    text = data.get('text', '')
    event = parse_alexa(text)
    if not event:
        return jsonify({'error': 'Could not parse event'}), 400
    conn = get_db()
    conn.execute('''
        INSERT INTO events (id, name, date, time, endTime, location, members, color, notes)
        VALUES (:id, :name, :date, :time, :endTime, :location, :members, :color, :notes)
    ''', event)
    conn.commit()
    conn.close()
    return jsonify(event), 201

def parse_alexa(text):
    import re
    from datetime import timedelta
    lower = text.lower()
    today = datetime.today()

    # Date parsing
    date = None
    if 'today' in lower or 'tonight' in lower:
        date = today
    elif 'tomorrow' in lower:
        date = today + timedelta(days=1)
    else:
        days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
        for i, day in enumerate(days):
            if day in lower:
                diff = (i - today.weekday() + 7) % 7 or 7
                date = today + timedelta(days=diff)
                break
        if not date:
            months = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
                      'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
            for month, num in months.items():
                m = re.search(month + r'\s+(\d{1,2})', lower)
                if m:
                    date = datetime(today.year, num, int(m.group(1)))
                    break
    if not date:
        date = today

    # Time parsing
    time = None
    t = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', lower)
    if t:
        h = int(t.group(1))
        mins = int(t.group(2)) if t.group(2) else 0
        if t.group(3) == 'pm' and h != 12:
            h += 12
        if t.group(3) == 'am' and h == 12:
            h = 0
        time = f'{h:02d}:{mins:02d}'

    # Members
    family = ['mom','dad','jake','lily']
    members = [m for m in family if m in lower]

    # Clean up name
    name = text
    for pattern in [
        r'\b(today|tonight|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b',
        r'\d{1,2}(?::\d{2})?\s*(?:am|pm)',
        r'\b(at|on|for)\b',
    ]:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    for m in family:
        name = re.sub(r'\b'+m+r'\b', '', name, flags=re.IGNORECASE)
    name = ' '.join(name.split()).strip() or 'New Event'

    return {
        'id': str(uuid.uuid4()),
        'name': name,
        'date': date.strftime('%Y-%m-%d'),
        'time': time or '',
        'endTime': '',
        'location': '',
        'members': ','.join(members),
        'color': 'sky',
        'notes': 'Added via Alexa',
    }

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=False)
