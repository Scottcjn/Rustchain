# SPDX-License-Identifier: MIT

import sqlite3
from flask import Flask, request, jsonify, render_template_string
import json
import os

app = Flask(__name__)
DB_PATH = 'blockchain.db'

@app.route('/api/docs')
def swagger_ui():
    """Serve Swagger UI for the RustChain API documentation"""
    swagger_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>RustChain API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui.css" />
    <style>
        html {
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }
        *, *:before, *:after {
            box-sizing: inherit;
        }
        body {
            margin: 0;
            background: #fafafa;
        }
        .swagger-ui .topbar {
            background-color: #89bf04;
        }
        .swagger-ui .topbar .download-url-wrapper input[type=text] {
            border: 2px solid #89bf04;
        }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: '/api/openapi.json',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                validatorUrl: null,
                tryItOutEnabled: true,
                supportedSubmitMethods: ['get', 'post', 'put', 'delete', 'patch'],
                onComplete: function() {
                    console.log('Swagger UI loaded');
                },
                docExpansion: 'list',
                filter: true,
                showRequestHeaders: true
            });
        };
    </script>
</body>
</html>
    '''
    return render_template_string(swagger_html)

@app.route('/api/openapi.json')
def openapi_spec():
    """Serve OpenAPI specification as JSON"""
    try:
        # Check if openapi.yaml exists
        if os.path.exists('openapi.yaml'):
            import yaml
            with open('openapi.yaml', 'r') as f:
                spec = yaml.safe_load(f)
            return jsonify(spec)
        else:
            # Return minimal spec if file doesn't exist
            minimal_spec = {
                "openapi": "3.0.3",
                "info": {
                    "title": "RustChain Node API",
                    "version": "2.2.1",
                    "description": "RustChain blockchain node API"
                },
                "servers": [
                    {"url": "http://localhost:5000", "description": "Local development node"}
                ],
                "paths": {
                    "/api/stats": {
                        "get": {
                            "summary": "Get node statistics",
                            "tags": ["blockchain"],
                            "responses": {
                                "200": {
                                    "description": "Node statistics",
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {
                                                    "status": {"type": "string"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            return jsonify(minimal_spec)
    except Exception as e:
        return jsonify({"error": f"Failed to load OpenAPI spec: {str(e)}"}), 500

@app.route('/api/validation/report')
def validation_report():
    """Get latest API validation report"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check if validation table exists
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='api_validation_reports'
            ''')

            if not cursor.fetchone():
                return jsonify({"error": "No validation reports available"}), 404

            # Get latest report
            cursor.execute('''
                SELECT report_data FROM api_validation_reports
                ORDER BY timestamp DESC LIMIT 1
            ''')

            row = cursor.fetchone()
            if row:
                return jsonify(json.loads(row[0]))
            else:
                return jsonify({"error": "No validation reports found"}), 404

    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route('/api/validation/history')
def validation_history():
    """Get validation report history"""
    try:
        limit = request.args.get('limit', 10, type=int)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT timestamp, total_endpoints, successful_endpoints,
                       failed_endpoints, success_rate, node_accessible
                FROM api_validation_reports
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))

            reports = []
            for row in cursor.fetchall():
                reports.append({
                    "timestamp": row[0],
                    "total_endpoints": row[1],
                    "successful_endpoints": row[2],
                    "failed_endpoints": row[3],
                    "success_rate": row[4],
                    "node_accessible": bool(row[5])
                })

            return jsonify({"reports": reports})

    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
