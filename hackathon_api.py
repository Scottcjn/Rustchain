// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from functools import wraps
import hashlib
import os

DB_PATH = "rustchain.db"

app = Flask(__name__)

# Initialize hackathon database tables
def init_hackathon_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Hackathon registrations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hackathon_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT UNIQUE NOT NULL,
                github_username TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                team_members TEXT,
                category TEXT NOT NULL,
                registration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')

        # Submissions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hackathon_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL,
                github_repo TEXT NOT NULL,
                project_title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                demo_url TEXT,
                submission_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                technical_score REAL DEFAULT 0,
                innovation_score REAL DEFAULT 0,
                usefulness_score REAL DEFAULT 0,
                presentation_score REAL DEFAULT 0,
                total_score REAL DEFAULT 0,
                people_choice_votes INTEGER DEFAULT 0,
                creativity_votes INTEGER DEFAULT 0,
                FOREIGN KEY (team_name) REFERENCES hackathon_registrations (team_name)
            )
        ''')

        # Voting table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hackathon_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_address TEXT NOT NULL,
                submission_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,
                vote_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(voter_address, submission_id, vote_type),
                FOREIGN KEY (submission_id) REFERENCES hackathon_submissions (id)
            )
        ''')

        # Prize distribution tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prize_distributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL,
                category TEXT NOT NULL,
                position INTEGER NOT NULL,
                rtc_amount REAL NOT NULL,
                wallet_address TEXT NOT NULL,
                transaction_hash TEXT,
                distributed BOOLEAN DEFAULT FALSE,
                distribution_time TIMESTAMP
            )
        ''')

        conn.commit()

# Prize structure configuration
PRIZE_STRUCTURE = {
    "Best DApp": {"1st": 75, "2nd": 40, "3rd": 20},
    "Best Tool/Library": {"1st": 75, "2nd": 40, "3rd": 20},
    "Best Integration": {"1st": 75, "2nd": 40, "3rd": 20},
    "People's Choice": {"1st": 50},
    "Most Creative": {"1st": 45}
}

def validate_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"error": "API key required"}), 401

        expected_key = hashlib.sha256(b"rustchain_hackathon_2024").hexdigest()[:32]
        if api_key != expected_key:
            return jsonify({"error": "Invalid API key"}), 401

        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/hackathon/register', methods=['POST'])
@validate_api_key
def register_team():
    try:
        data = request.get_json()
        required_fields = ['team_name', 'github_username', 'wallet_address', 'category']

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Validate category
        valid_categories = ["Best DApp", "Best Tool/Library", "Best Integration"]
        if data['category'] not in valid_categories:
            return jsonify({"error": "Invalid category"}), 400

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute('''
                    INSERT INTO hackathon_registrations
                    (team_name, github_username, wallet_address, team_members, category)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    data['team_name'],
                    data['github_username'],
                    data['wallet_address'],
                    data.get('team_members', ''),
                    data['category']
                ))
                conn.commit()

                return jsonify({
                    "success": True,
                    "message": "Team registered successfully",
                    "team_name": data['team_name']
                }), 201

            except sqlite3.IntegrityError:
                return jsonify({"error": "Team name already registered"}), 409

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hackathon/submit', methods=['POST'])
@validate_api_key
def submit_project():
    try:
        data = request.get_json()
        required_fields = ['team_name', 'github_repo', 'project_title', 'description', 'category']

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check if team is registered
            cursor.execute('SELECT id FROM hackathon_registrations WHERE team_name = ?', (data['team_name'],))
            if not cursor.fetchone():
                return jsonify({"error": "Team not registered"}), 400

            # Check for existing submission
            cursor.execute('SELECT id FROM hackathon_submissions WHERE team_name = ?', (data['team_name'],))
            existing = cursor.fetchone()

            if existing:
                # Update existing submission
                cursor.execute('''
                    UPDATE hackathon_submissions
                    SET github_repo = ?, project_title = ?, description = ?,
                        category = ?, demo_url = ?, submission_time = CURRENT_TIMESTAMP
                    WHERE team_name = ?
                ''', (
                    data['github_repo'],
                    data['project_title'],
                    data['description'],
                    data['category'],
                    data.get('demo_url', ''),
                    data['team_name']
                ))
                message = "Submission updated successfully"
            else:
                # Create new submission
                cursor.execute('''
                    INSERT INTO hackathon_submissions
                    (team_name, github_repo, project_title, description, category, demo_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    data['team_name'],
                    data['github_repo'],
                    data['project_title'],
                    data['description'],
                    data['category'],
                    data.get('demo_url', '')
                ))
                message = "Project submitted successfully"

            conn.commit()
            return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hackathon/vote', methods=['POST'])
@validate_api_key
def cast_vote():
    try:
        data = request.get_json()
        required_fields = ['voter_address', 'submission_id', 'vote_type']

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        if data['vote_type'] not in ['people_choice', 'creativity']:
            return jsonify({"error": "Invalid vote type"}), 400

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            try:
                # Record vote
                cursor.execute('''
                    INSERT INTO hackathon_votes (voter_address, submission_id, vote_type)
                    VALUES (?, ?, ?)
                ''', (data['voter_address'], data['submission_id'], data['vote_type']))

                # Update submission vote count
                if data['vote_type'] == 'people_choice':
                    cursor.execute('''
                        UPDATE hackathon_submissions
                        SET people_choice_votes = people_choice_votes + 1
                        WHERE id = ?
                    ''', (data['submission_id'],))
                else:
                    cursor.execute('''
                        UPDATE hackathon_submissions
                        SET creativity_votes = creativity_votes + 1
                        WHERE id = ?
                    ''', (data['submission_id'],))

                conn.commit()
                return jsonify({"success": True, "message": "Vote recorded"}), 200

            except sqlite3.IntegrityError:
                return jsonify({"error": "Already voted for this submission"}), 409

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hackathon/leaderboard/<category>')
def get_leaderboard(category):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            if category == "people_choice":
                cursor.execute('''
                    SELECT team_name, project_title, people_choice_votes as score
                    FROM hackathon_submissions
                    WHERE people_choice_votes > 0
                    ORDER BY people_choice_votes DESC
                    LIMIT 10
                ''')
            elif category == "creativity":
                cursor.execute('''
                    SELECT team_name, project_title, creativity_votes as score
                    FROM hackathon_submissions
                    WHERE creativity_votes > 0
                    ORDER BY creativity_votes DESC
                    LIMIT 10
                ''')
            else:
                cursor.execute('''
                    SELECT team_name, project_title, total_score as score
                    FROM hackathon_submissions
                    WHERE category = ? AND total_score > 0
                    ORDER BY total_score DESC
                    LIMIT 10
                ''', (category,))

            results = cursor.fetchall()
            leaderboard = []

            for i, (team_name, project_title, score) in enumerate(results):
                leaderboard.append({
                    "position": i + 1,
                    "team_name": team_name,
                    "project_title": project_title,
                    "score": score
                })

            return jsonify({
                "category": category,
                "leaderboard": leaderboard,
                "total_entries": len(leaderboard)
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hackathon/submissions')
def get_submissions():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.*, r.wallet_address, r.github_username
                FROM hackathon_submissions s
                JOIN hackathon_registrations r ON s.team_name = r.team_name
                ORDER BY s.submission_time DESC
            ''')

            submissions = []
            for row in cursor.fetchall():
                submissions.append({
                    "id": row[0],
                    "team_name": row[1],
                    "github_repo": row[2],
                    "project_title": row[3],
                    "description": row[4],
                    "category": row[5],
                    "demo_url": row[6],
                    "submission_time": row[7],
                    "scores": {
                        "technical": row[8],
                        "innovation": row[9],
                        "usefulness": row[10],
                        "presentation": row[11],
                        "total": row[12]
                    },
                    "votes": {
                        "people_choice": row[13],
                        "creativity": row[14]
                    },
                    "wallet_address": row[15],
                    "github_username": row[16]
                })

            return jsonify({"submissions": submissions})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hackathon/score', methods=['POST'])
@validate_api_key
def update_scores():
    try:
        data = request.get_json()
        required_fields = ['submission_id', 'technical_score', 'innovation_score',
                          'usefulness_score', 'presentation_score']

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        total_score = (data['technical_score'] * 0.3 +
                      data['innovation_score'] * 0.25 +
                      data['usefulness_score'] * 0.25 +
                      data['presentation_score'] * 0.2)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE hackathon_submissions
                SET technical_score = ?, innovation_score = ?,
                    usefulness_score = ?, presentation_score = ?, total_score = ?
                WHERE id = ?
            ''', (
                data['technical_score'], data['innovation_score'],
                data['usefulness_score'], data['presentation_score'],
                total_score, data['submission_id']
            ))
            conn.commit()

            return jsonify({
                "success": True,
                "total_score": total_score,
                "message": "Scores updated successfully"
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hackathon/prizes/calculate', methods=['POST'])
@validate_api_key
def calculate_prizes():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Clear existing prize calculations
            cursor.execute('DELETE FROM prize_distributions')

            prize_allocations = []

            # Calculate prizes for each category
            for category in ["Best DApp", "Best Tool/Library", "Best Integration"]:
                cursor.execute('''
                    SELECT s.team_name, r.wallet_address, s.total_score
                    FROM hackathon_submissions s
                    JOIN hackathon_registrations r ON s.team_name = r.team_name
                    WHERE s.category = ? AND s.total_score > 0
                    ORDER BY s.total_score DESC
                    LIMIT 3
                ''', (category,))

                results = cursor.fetchall()
                positions = ["1st", "2nd", "3rd"]

                for i, (team_name, wallet_addr, score) in enumerate(results):
                    position = positions[i]
                    rtc_amount = PRIZE_STRUCTURE[category][position]

                    cursor.execute('''
                        INSERT INTO prize_distributions
                        (team_name, category, position, rtc_amount, wallet_address)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (team_name, category, i + 1, rtc_amount, wallet_addr))

                    prize_allocations.append({
                        "team_name": team_name,
                        "category": category,
                        "position": position,
                        "rtc_amount": rtc_amount,
                        "wallet_address": wallet_addr
                    })

            # People's Choice Award
            cursor.execute('''
                SELECT s.team_name, r.wallet_address, s.people_choice_votes
                FROM hackathon_submissions s
                JOIN hackathon_registrations r ON s.team_name = r.team_name
                WHERE s.people_choice_votes > 0
                ORDER BY s.people_choice_votes DESC
                LIMIT 1
            ''')

            result = cursor.fetchone()
            if result:
                team_name, wallet_addr, votes = result
                rtc_amount = PRIZE_STRUCTURE["People's Choice"]["1st"]

                cursor.execute('''
                    INSERT INTO prize_distributions
                    (team_name, category, position, rtc_amount, wallet_address)
                    VALUES (?, ?, ?, ?, ?)
                ''', (team_name, "People's Choice", 1, rtc_amount, wallet_addr))

                prize_allocations.append({
                    "team_name": team_name,
                    "category": "People's Choice",
                    "position": "1st",
                    "rtc_amount": rtc_amount,
                    "wallet_address": wallet_addr
                })

            # Most Creative Award
            cursor.execute('''
                SELECT s.team_name, r.wallet_address, s.creativity_votes
                FROM hackathon_submissions s
                JOIN hackathon_registrations r ON s.team_name = r.team_name
                WHERE s.creativity_votes > 0
                ORDER BY s.creativity_votes DESC
                LIMIT 1
            ''')

            result = cursor.fetchone()
            if result:
                team_name, wallet_addr, votes = result
                rtc_amount = PRIZE_STRUCTURE["Most Creative"]["1st"]

                cursor.execute('''
                    INSERT INTO prize_distributions
                    (team_name, category, position, rtc_amount, wallet_address)
                    VALUES (?, ?, ?, ?, ?)
                ''', (team_name, "Most Creative", 1, rtc_amount, wallet_addr))

                prize_allocations.append({
                    "team_name": team_name,
                    "category": "Most Creative",
                    "position": "1st",
                    "rtc_amount": rtc_amount,
                    "wallet_address": wallet_addr
                })

            conn.commit()

            total_rtc = sum(allocation["rtc_amount"] for allocation in prize_allocations)

            return jsonify({
                "success": True,
                "prize_allocations": prize_allocations,
                "total_rtc_distributed": total_rtc,
                "prize_pool": 500
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hackathon/prizes/distribute', methods=['POST'])
@validate_api_key
def distribute_prizes():
    try:
        data = request.get_json()
        transaction_hashes = data.get('transaction_hashes', {})

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM prize_distributions WHERE distributed = FALSE')
            pending_distributions = cursor.fetchall()

            distributed_count = 0
            for dist in pending_distributions:
                prize_id, team_name, category, position, rtc_amount, wallet_addr = dist[:6]

                tx_hash = transaction_hashes.get(f"{team_name}_{category}")
                if tx_hash:
                    cursor.execute('''
                        UPDATE prize_distributions
                        SET distributed = TRUE, transaction_hash = ?, distribution_time = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (tx_hash, prize_id))
                    distributed_count += 1

            conn.commit()

            return jsonify({
                "success": True,
                "distributed_count": distributed_count,
                "message": f"Distributed prizes to {distributed_count} winners"
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hackathon/status')
def hackathon_status():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get registration count
            cursor.execute('SELECT COUNT(*) FROM hackathon_registrations')
            registrations = cursor.fetchone()[0]

            # Get submission count
            cursor.execute('SELECT COUNT(*) FROM hackathon_submissions')
            submissions = cursor.fetchone()[0]

            # Get total votes cast
            cursor.execute('SELECT COUNT(*) FROM hackathon_votes')
            total_votes = cursor.fetchone()[0]

            # Get prize distribution status
            cursor.execute('SELECT COUNT(*) FROM prize_distributions WHERE distributed = TRUE')
            distributed_prizes = cursor.fetchone()[0]

            cursor.execute('SELECT SUM(rtc_amount) FROM prize_distributions WHERE distributed = TRUE')
            distributed_rtc = cursor.fetchone()[0] or 0

            return jsonify({
                "hackathon_stats": {
                    "registrations": registrations,
                    "submissions": submissions,
                    "total_votes": total_votes,
                    "distributed_prizes": distributed_prizes,
                    "distributed_rtc": distributed_rtc,
                    "prize_pool": 500
                },
                "timeline": {
                    "registration_period": "1 week",
                    "building_period": "2 weeks",
                    "judging_period": "1 week"
                },
                "categories": list(PRIZE_STRUCTURE.keys())
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_hackathon_db()
    app.run(debug=True, port=5001)
