// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import logging
import json
import datetime
from contextlib import contextmanager

DB_PATH = 'hackathon.db'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """Database connection context manager"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

def init_database():
    """Initialize hackathon database schema"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Teams table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                leader_github TEXT NOT NULL,
                member_count INTEGER DEFAULT 1,
                members TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'registered'
            )
        ''')

        # Projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                github_url TEXT NOT NULL,
                category TEXT NOT NULL,
                technologies TEXT,
                demo_url TEXT,
                submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'submitted',
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        ''')

        # Judges table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS judges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                github TEXT,
                role TEXT,
                expertise TEXT,
                active INTEGER DEFAULT 1
            )
        ''')

        # Scores table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                judge_id INTEGER NOT NULL,
                technical_quality INTEGER CHECK(technical_quality >= 0 AND technical_quality <= 100),
                innovation INTEGER CHECK(innovation >= 0 AND innovation <= 100),
                usefulness INTEGER CHECK(usefulness >= 0 AND usefulness <= 100),
                presentation INTEGER CHECK(presentation >= 0 AND presentation <= 100),
                total_score REAL,
                comments TEXT,
                scored_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id),
                FOREIGN KEY (judge_id) REFERENCES judges (id),
                UNIQUE(project_id, judge_id)
            )
        ''')

        # Public votes table (for People's Choice)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS public_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                voter_github TEXT NOT NULL,
                vote_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id),
                UNIQUE(project_id, voter_github)
            )
        ''')

        # Prizes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prizes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                place INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                project_id INTEGER,
                awarded_date TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        ''')

        conn.commit()
        logger.info("Database initialized successfully")

def register_team(team_name, leader_github, members_list=None):
    """Register a new team for the hackathon"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        members_json = json.dumps(members_list) if members_list else json.dumps([leader_github])
        member_count = len(members_list) if members_list else 1

        if member_count > 4:
            raise ValueError("Team size cannot exceed 4 members")

        cursor.execute('''
            INSERT INTO teams (name, leader_github, member_count, members)
            VALUES (?, ?, ?, ?)
        ''', (team_name, leader_github, member_count, members_json))

        team_id = cursor.lastrowid
        conn.commit()
        logger.info(f"Team '{team_name}' registered with ID {team_id}")
        return team_id

def submit_project(team_id, title, description, github_url, category, technologies=None, demo_url=None):
    """Submit a project for judging"""
    valid_categories = ['Best DApp', 'Best Tool/Library', 'Best Integration']

    if category not in valid_categories:
        raise ValueError(f"Invalid category. Must be one of: {valid_categories}")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if team exists
        cursor.execute('SELECT id FROM teams WHERE id = ?', (team_id,))
        if not cursor.fetchone():
            raise ValueError("Team not found")

        tech_json = json.dumps(technologies) if technologies else None

        cursor.execute('''
            INSERT INTO projects (team_id, title, description, github_url, category, technologies, demo_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (team_id, title, description, github_url, category, tech_json, demo_url))

        project_id = cursor.lastrowid
        conn.commit()
        logger.info(f"Project '{title}' submitted with ID {project_id}")
        return project_id

def add_judge(name, github=None, role=None, expertise=None):
    """Add a judge to the system"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO judges (name, github, role, expertise)
            VALUES (?, ?, ?, ?)
        ''', (name, github, role, expertise))

        judge_id = cursor.lastrowid
        conn.commit()
        logger.info(f"Judge '{name}' added with ID {judge_id}")
        return judge_id

def submit_score(project_id, judge_id, technical, innovation, usefulness, presentation, comments=None):
    """Submit judge scores for a project"""
    if not all(0 <= score <= 100 for score in [technical, innovation, usefulness, presentation]):
        raise ValueError("All scores must be between 0 and 100")

    # Calculate weighted total: Technical (30%), Innovation (25%), Usefulness (25%), Presentation (20%)
    total_score = (technical * 0.30) + (innovation * 0.25) + (usefulness * 0.25) + (presentation * 0.20)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO scores
            (project_id, judge_id, technical_quality, innovation, usefulness, presentation, total_score, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, judge_id, technical, innovation, usefulness, presentation, total_score, comments))

        conn.commit()
        logger.info(f"Score submitted for project {project_id} by judge {judge_id}")
        return total_score

def cast_public_vote(project_id, voter_github):
    """Cast a public vote for People's Choice award"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO public_votes (project_id, voter_github)
                VALUES (?, ?)
            ''', (project_id, voter_github))
            conn.commit()
            logger.info(f"Vote cast for project {project_id} by {voter_github}")
        except sqlite3.IntegrityError:
            raise ValueError("User has already voted for this project")

def calculate_rankings():
    """Calculate final rankings for all categories"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        rankings = {}

        # Regular categories
        for category in ['Best DApp', 'Best Tool/Library', 'Best Integration']:
            cursor.execute('''
                SELECT p.id, p.title, t.name as team_name, AVG(s.total_score) as avg_score
                FROM projects p
                JOIN teams t ON p.team_id = t.id
                LEFT JOIN scores s ON p.id = s.project_id
                WHERE p.category = ?
                GROUP BY p.id
                ORDER BY avg_score DESC
            ''', (category,))

            rankings[category] = cursor.fetchall()

        # People's Choice (by vote count)
        cursor.execute('''
            SELECT p.id, p.title, t.name as team_name, COUNT(pv.id) as vote_count
            FROM projects p
            JOIN teams t ON p.team_id = t.id
            LEFT JOIN public_votes pv ON p.id = pv.project_id
            GROUP BY p.id
            ORDER BY vote_count DESC
        ''')

        rankings['Peoples Choice'] = cursor.fetchall()

        # Most Creative (highest innovation score)
        cursor.execute('''
            SELECT p.id, p.title, t.name as team_name, AVG(s.innovation) as avg_innovation
            FROM projects p
            JOIN teams t ON p.team_id = t.id
            LEFT JOIN scores s ON p.id = s.project_id
            GROUP BY p.id
            ORDER BY avg_innovation DESC
        ''')

        rankings['Most Creative'] = cursor.fetchall()

        return rankings

def award_prizes():
    """Calculate and award prizes based on rankings"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Prize structure
        prize_structure = {
            'Best DApp': {1: 75, 2: 40, 3: 20},
            'Best Tool/Library': {1: 75, 2: 40, 3: 20},
            'Best Integration': {1: 75, 2: 40, 3: 20},
            'Peoples Choice': {1: 50},
            'Most Creative': {1: 45}
        }

        rankings = calculate_rankings()
        awarded_prizes = []

        for category, places in prize_structure.items():
            if category in rankings:
                for place, amount in places.items():
                    if len(rankings[category]) >= place:
                        project = rankings[category][place - 1]
                        project_id = project['id']

                        cursor.execute('''
                            INSERT OR REPLACE INTO prizes (category, place, amount, project_id, awarded_date)
                            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ''', (category, place, amount, project_id))

                        awarded_prizes.append({
                            'category': category,
                            'place': place,
                            'amount': amount,
                            'project_title': project['title'],
                            'team_name': project['team_name']
                        })

        conn.commit()
        logger.info(f"Awarded {len(awarded_prizes)} prizes")
        return awarded_prizes

def get_hackathon_stats():
    """Get overall hackathon statistics"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        stats = {}

        # Team count
        cursor.execute('SELECT COUNT(*) as count FROM teams')
        stats['teams'] = cursor.fetchone()['count']

        # Project count by category
        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM projects
            GROUP BY category
        ''')
        stats['projects_by_category'] = dict(cursor.fetchall())

        # Total projects
        cursor.execute('SELECT COUNT(*) as count FROM projects')
        stats['total_projects'] = cursor.fetchone()['count']

        # Total votes
        cursor.execute('SELECT COUNT(*) as count FROM public_votes')
        stats['total_votes'] = cursor.fetchone()['count']

        # Judging progress
        cursor.execute('''
            SELECT
                COUNT(DISTINCT p.id) as total_projects,
                COUNT(DISTINCT s.project_id) as scored_projects
            FROM projects p
            LEFT JOIN scores s ON p.id = s.project_id
        ''')
        judging = cursor.fetchone()
        stats['judging_progress'] = {
            'total': judging['total_projects'],
            'completed': judging['scored_projects']
        }

        return stats
