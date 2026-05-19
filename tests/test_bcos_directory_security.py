# SPDX-License-Identifier: MIT

import json
import re
import sqlite3

import bcos_directory


def test_bcos_directory_secret_key_uses_environment(monkeypatch):
    monkeypatch.setenv('BCOS_DIRECTORY_SECRET_KEY', 'configured-secret')

    assert bcos_directory.load_secret_key() == 'configured-secret'


def test_bcos_directory_secret_key_fallback_is_not_public_constant(monkeypatch):
    monkeypatch.delenv('BCOS_DIRECTORY_SECRET_KEY', raising=False)

    secret = bcos_directory.load_secret_key()

    assert secret != 'bcos-directory-dev-key'
    assert re.fullmatch(r'[0-9a-f]{64}', secret)


def test_bcos_directory_debug_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv('BCOS_DIRECTORY_DEBUG', raising=False)
    assert bcos_directory.debug_enabled() is False

    monkeypatch.setenv('BCOS_DIRECTORY_DEBUG', 'true')
    assert bcos_directory.debug_enabled() is True


def test_bcos_directory_host_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv('BCOS_DIRECTORY_HOST', raising=False)

    assert bcos_directory.server_host() == '127.0.0.1'


def test_bcos_directory_project_load_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / 'bcos_directory.db'
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'projects.json').write_text(json.dumps({
        'projects': [{
            'name': 'RustChain',
            'url': 'https://example.test/rustchain',
            'github_repo': 'Scottcjn/Rustchain',
            'bcos_tier': 'L1',
            'latest_sha': 'abc123',
            'sbom_hash': 'hash-one',
            'review_note': 'initial review',
            'category': 'chain',
        }]
    }))
    monkeypatch.setattr(bcos_directory, 'DATABASE', str(db_path))
    monkeypatch.chdir(tmp_path)

    bcos_directory.init_db()
    bcos_directory.load_projects_from_json()
    bcos_directory.load_projects_from_json()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT name, github_repo, latest_sha FROM projects'
        ).fetchall()
        indexes = conn.execute(
            "PRAGMA index_list('projects')"
        ).fetchall()

    assert rows == [('RustChain', 'Scottcjn/Rustchain', 'abc123')]
    assert any(row[1] == 'idx_projects_github_repo' and row[2] for row in indexes)


def test_bcos_directory_init_deduplicates_existing_projects_before_unique_index(tmp_path, monkeypatch):
    db_path = tmp_path / 'bcos_directory.db'
    monkeypatch.setattr(bcos_directory, 'DATABASE', str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                github_repo TEXT NOT NULL,
                bcos_tier TEXT NOT NULL,
                latest_sha TEXT,
                sbom_hash TEXT,
                review_note TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.executemany('''
            INSERT INTO projects
            (name, url, github_repo, bcos_tier, latest_sha, sbom_hash, review_note, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            ('Old RustChain', 'https://old.example', 'Scottcjn/Rustchain', 'L1', 'old', None, None, 'chain'),
            ('New RustChain', 'https://new.example', 'Scottcjn/Rustchain', 'L2', 'new', None, None, 'chain'),
        ])

    bcos_directory.init_db()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT name, github_repo, latest_sha FROM projects'
        ).fetchall()

    assert rows == [('New RustChain', 'Scottcjn/Rustchain', 'new')]
