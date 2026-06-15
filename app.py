from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime, timedelta
import requests
import re

app = Flask(__name__)
CORS(app)

DB_PATH = 'data/studyhub.db'
OLLAMA_DEFAULT_URL = 'http://localhost:11434'

os.makedirs('data', exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.executescript('''
    CREATE TABLE IF NOT EXISTS paths (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        created_at TIMESTAMP,
        target_date TEXT,
        daily_minutes INTEGER DEFAULT 120
    );
    
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY,
        path_id INTEGER,
        title TEXT,
        description TEXT,
        order_num INTEGER,
        FOREIGN KEY(path_id) REFERENCES paths(id)
    );
    
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY,
        module_id INTEGER,
        title TEXT,
        description TEXT,
        done INTEGER DEFAULT 0,
        done_at TIMESTAMP,
        est_minutes INTEGER DEFAULT 20,
        FOREIGN KEY(module_id) REFERENCES modules(id)
    );
    
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY,
        module_id INTEGER,
        content TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY(module_id) REFERENCES modules(id)
    );
    
    CREATE TABLE IF NOT EXISTS tools (
        id INTEGER PRIMARY KEY,
        path_id INTEGER,
        name TEXT,
        url TEXT,
        progress REAL DEFAULT 0,
        FOREIGN KEY(path_id) REFERENCES paths(id)
    );
    
    CREATE TABLE IF NOT EXISTS plan_days (
        id INTEGER PRIMARY KEY,
        path_id INTEGER,
        day_num INTEGER,
        tasks TEXT,
        done INTEGER DEFAULT 0,
        FOREIGN KEY(path_id) REFERENCES paths(id)
    );
    
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id INTEGER PRIMARY KEY,
        module_id INTEGER,
        question TEXT,
        user_answer TEXT,
        correct_answer TEXT,
        score REAL,
        created_at TIMESTAMP,
        FOREIGN KEY(module_id) REFERENCES modules(id)
    );
    
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    ''')
    
    conn.commit()
    conn.close()

init_db()

def seed_data():
    """Seed default AWS course data."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM paths')
    if c.fetchone()[0] > 0:
        conn.close()
        return
    
    target_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    c.execute('''INSERT INTO paths (name, created_at, target_date, daily_minutes)
                 VALUES (?, ?, ?, ?)''',
              ('AWS Solutions Architect', datetime.now().isoformat(), target_date, 120))
    path_id = c.lastrowid
    
    modules_data = [
        ('IAM & Access Management', 'Identity and Access Management', 1),
        ('EC2 & Compute', 'Elastic Compute Cloud', 2),
        ('Storage Services', 'S3, EBS, EFS', 3),
        ('Databases', 'RDS, DynamoDB', 4),
        ('Networking', 'VPC, Route53, CloudFront', 5),
        ('Application Services', 'SQS, SNS', 6),
        ('Monitoring', 'CloudWatch, CloudTrail', 7),
        ('Security', 'Encryption, KMS', 8),
    ]
    
    for title, desc, order in modules_data:
        c.execute('''INSERT INTO modules (path_id, title, description, order_num)
                     VALUES (?, ?, ?, ?)''',
                  (path_id, title, desc, order))
        module_id = c.lastrowid
        for i in range(1, 6):
            c.execute('''INSERT INTO lessons (module_id, title, description, done, est_minutes)
                         VALUES (?, ?, ?, ?, ?)''',
                      (module_id, f'Lesson {i}', f'Learn about {title}', 0, 20))
    
    tools_data = [
        ('Skill Builder', 'https://skillbuilder.aws.com'),
        ('KodeKloud', 'https://kodekloud.com'),
        ('TryHackMe', 'https://tryhackme.com'),
        ('NotebookLM', 'https://notebooklm.google.com'),
        ('Obsidian', 'obsidian://'),
        ('Odyssey', 'https://aws.amazon.com/training/odyssey/'),
        ('GitHub Pack', 'https://education.github.com/pack'),
    ]
    
    for tool_name, tool_url in tools_data:
        c.execute('''INSERT INTO tools (path_id, name, url, progress)
                     VALUES (?, ?, ?, ?)''',
                  (path_id, tool_name, tool_url, 0))
    
    for day in range(1, 31):
        module_num = ((day - 1) % 8) + 1
        c.execute('''INSERT INTO plan_days (path_id, day_num, tasks, done)
                     VALUES (?, ?, ?, ?)''',
                  (path_id, day, f'Study Module {module_num} lessons + Quiz + Notes', 0))
    
    conn.commit()
    conn.close()

seed_data()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/paths', methods=['GET'])
def get_paths():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM paths')
    paths = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(paths)

@app.route('/api/modules/<int:path_id>', methods=['GET'])
def get_modules(path_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM modules WHERE path_id=? ORDER BY order_num', (path_id,))
    modules = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(modules)

@app.route('/api/lessons/<int:module_id>', methods=['GET'])
def get_lessons(module_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM lessons WHERE module_id=? ORDER BY order_num', (module_id,))
    lessons = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(lessons)

@app.route('/api/lessons/<int:lesson_id>/toggle', methods=['POST'])
def toggle_lesson(lesson_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT done FROM lessons WHERE id=?', (lesson_id,))
    done = c.fetchone()[0]
    new_done = 1 - done
    done_at = datetime.now().isoformat() if new_done else None
    c.execute('UPDATE lessons SET done=?, done_at=? WHERE id=?', (new_done, done_at, lesson_id))
    conn.commit()
    conn.close()
    return jsonify({'done': new_done})

@app.route('/api/notes/<int:module_id>', methods=['GET'])
def get_notes(module_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM notes WHERE module_id=? ORDER BY updated_at DESC', (module_id,))
    notes = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(notes)

@app.route('/api/notes', methods=['POST'])
def save_notes():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id FROM notes WHERE module_id=?', (data.get('module_id'),))
    existing = c.fetchone()
    
    now = datetime.now().isoformat()
    if existing:
        c.execute('UPDATE notes SET content=?, updated_at=? WHERE module_id=?',
                  (data.get('content'), now, data.get('module_id')))
    else:
        c.execute('INSERT INTO notes (module_id, content, created_at, updated_at) VALUES (?, ?, ?, ?)',
                  (data.get('module_id'), data.get('content'), now, now))
    
    conn.commit()
    conn.close()
    return jsonify({'message': 'Notes saved'})

@app.route('/api/tools/<int:path_id>', methods=['GET'])
def get_tools(path_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM tools WHERE path_id=?', (path_id,))
    tools = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(tools)

@app.route('/api/tools/<int:tool_id>', methods=['PUT'])
def update_tool(tool_id):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE tools SET progress=? WHERE id=?', (data.get('progress'), tool_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Tool updated'})

@app.route('/api/plan/<int:path_id>', methods=['GET'])
def get_plan(path_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM plan_days WHERE path_id=? ORDER BY day_num', (path_id,))
    plan = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(plan)

@app.route('/api/plan/<int:day_id>/toggle', methods=['POST'])
def toggle_plan_day(day_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT done FROM plan_days WHERE id=?', (day_id,))
    done = c.fetchone()[0]
    new_done = 1 - done
    c.execute('UPDATE plan_days SET done=? WHERE id=?', (new_done, day_id))
    conn.commit()
    conn.close()
    return jsonify({'done': new_done})

@app.route('/api/analytics/<int:path_id>', methods=['GET'])
def get_analytics(path_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''SELECT COUNT(*) as total, SUM(CASE WHEN done=1 THEN 1 ELSE 0 END) as completed
                 FROM lessons l
                 JOIN modules m ON l.module_id = m.id
                 WHERE m.path_id=?''', (path_id,))
    progress = dict(c.fetchone())
    
    c.execute('''SELECT COUNT(DISTINCT DATE(done_at)) as days_studied FROM lessons
                 JOIN modules m ON lessons.module_id = m.id
                 WHERE m.path_id=? AND done=1''', (path_id,))
    days_studied = c.fetchone()[0] or 0
    
    conn.close()
    return jsonify({'progress': progress, 'days_studied': days_studied})

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    data = request.json
    query = data.get('query', '')
    model = data.get('model', 'llama3.1')
    
    try:
        ollama_url = app.config.get('OLLAMA_URL', OLLAMA_DEFAULT_URL)
        response = requests.post(f'{ollama_url}/api/generate',
                               json={'model': model, 'prompt': query, 'stream': False},
                               timeout=30)
        if response.status_code == 200:
            return jsonify({'success': True, 'response': response.json().get('response', '')})
        return jsonify({'success': False, 'error': 'Ollama error'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/quiz', methods=['POST'])
def generate_quiz():
    data = request.json
    content = data.get('content', '')
    num_questions = data.get('num_questions', 5)
    model = data.get('model', 'llama3.1')
    
    prompt = f'''Generate {num_questions} multiple-choice quiz questions from this content:

{content}

Format as JSON:
{{
  "questions": [
    {{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A", "explanation": "..."}}
  ]
}}'''
    
    try:
        ollama_url = app.config.get('OLLAMA_URL', OLLAMA_DEFAULT_URL)
        response = requests.post(f'{ollama_url}/api/generate',
                               json={'model': model, 'prompt': prompt, 'stream': False},
                               timeout=60)
        if response.status_code == 200:
            resp_text = response.json().get('response', '')
            match = re.search(r'{.*}', resp_text, re.DOTALL)
            if match:
                quiz_json = json.loads(match.group())
                return jsonify({'success': True, 'quiz': quiz_json})
        return jsonify({'success': False, 'error': 'Quiz generation failed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/settings', methods=['GET', 'POST'])
def ai_settings():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT * FROM settings WHERE key LIKE "ollama%"')
        settings = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        return jsonify(settings)
    
    data = request.json
    for key, value in data.items():
        c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()
    
    if 'ollama_url' in data:
        app.config['OLLAMA_URL'] = data['ollama_url']
    
    return jsonify({'message': 'Settings saved'})

@app.route('/api/ai/test', methods=['POST'])
def test_ollama():
    data = request.json
    url = data.get('url', OLLAMA_DEFAULT_URL)
    
    try:
        response = requests.get(f'{url}/api/tags', timeout=5)
        if response.status_code == 200:
            models = [m['name'] for m in response.json().get('models', [])]
            return jsonify({'success': True, 'models': models})
        return jsonify({'success': False, 'error': 'Connection failed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='localhost', port=5050, debug=False)
