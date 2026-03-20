// SPDX-License-Identifier: MIT
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
                onFailure: function(err) {
                    console.error('Failed to load API spec:', err);
                }
            });
        };
    </script>
</body>
</html>
    '''
    return render_template_string(swagger_html)

@app.route('/api/openapi.json')
def openapi_spec():
    """Serve the OpenAPI specification for RustChain node API"""

    openapi_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "RustChain Node API",
            "description": "REST API for RustChain blockchain node operations including blocks, transactions, mining, and peer management",
            "version": "2.2.1",
            "contact": {
                "name": "RustChain Development Team",
                "url": "https://github.com/Scottcjn/Rustchain"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        },
        "servers": [
            {
                "url": "http://localhost:5000",
                "description": "Local development server"
            }
        ],
        "paths": {
            "/api/blocks": {
                "get": {
                    "summary": "Get all blocks",
                    "description": "Retrieve all blocks in the blockchain",
                    "tags": ["Blockchain"],
                    "responses": {
                        "200": {
                            "description": "List of blocks",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Block"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/blocks/{block_id}": {
                "get": {
                    "summary": "Get block by ID",
                    "description": "Retrieve a specific block by its ID",
                    "tags": ["Blockchain"],
                    "parameters": [
                        {
                            "name": "block_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                            "description": "Block ID"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Block details",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Block"}
                                }
                            }
                        },
                        "404": {
                            "description": "Block not found"
                        }
                    }
                }
            },
            "/api/transactions": {
                "get": {
                    "summary": "Get all transactions",
                    "description": "Retrieve all transactions from the blockchain",
                    "tags": ["Transactions"],
                    "responses": {
                        "200": {
                            "description": "List of transactions",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Transaction"}
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": "Create new transaction",
                    "description": "Submit a new transaction to the blockchain",
                    "tags": ["Transactions"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TransactionInput"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Transaction created successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Transaction"}
                                }
                            }
                        },
                        "400": {
                            "description": "Invalid transaction data"
                        }
                    }
                }
            },
            "/api/balance/{address}": {
                "get": {
                    "summary": "Get wallet balance",
                    "description": "Retrieve the balance for a specific wallet address",
                    "tags": ["Wallet"],
                    "parameters": [
                        {
                            "name": "address",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Wallet address"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Wallet balance",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "address": {"type": "string"},
                                            "balance": {"type": "number"}
                                        }
                                    }
                                }
                            }
                        },
                        "404": {
                            "description": "Address not found"
                        }
                    }
                }
            },
            "/api/mine": {
                "post": {
                    "summary": "Mine new block",
                    "description": "Start mining a new block with pending transactions",
                    "tags": ["Mining"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "miner_address": {
                                            "type": "string",
                                            "description": "Address to receive mining reward"
                                        }
                                    },
                                    "required": ["miner_address"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Block mined successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Block"}
                                }
                            }
                        },
                        "400": {
                            "description": "Mining failed"
                        }
                    }
                }
            },
            "/api/peers": {
                "get": {
                    "summary": "Get connected peers",
                    "description": "Retrieve list of connected network peers",
                    "tags": ["Network"],
                    "responses": {
                        "200": {
                            "description": "List of peers",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "host": {"type": "string"},
                                                "port": {"type": "integer"},
                                                "status": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/network/status": {
                "get": {
                    "summary": "Get network status",
                    "description": "Retrieve current network and node status information",
                    "tags": ["Network"],
                    "responses": {
                        "200": {
                            "description": "Network status",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "node_id": {"type": "string"},
                                            "version": {"type": "string"},
                                            "block_height": {"type": "integer"},
                                            "peer_count": {"type": "integer"},
                                            "sync_status": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "Block": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "index": {"type": "integer"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "data": {"type": "string"},
                        "previous_hash": {"type": "string"},
                        "hash": {"type": "string"},
                        "nonce": {"type": "integer"},
                        "transactions": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Transaction"}
                        }
                    },
                    "required": ["id", "index", "timestamp", "hash", "previous_hash"]
                },
                "Transaction": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "from_address": {"type": "string"},
                        "to_address": {"type": "string"},
                        "amount": {"type": "number"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "signature": {"type": "string"},
                        "hash": {"type": "string"}
                    },
                    "required": ["id", "from_address", "to_address", "amount", "timestamp"]
                },
                "TransactionInput": {
                    "type": "object",
                    "properties": {
                        "from_address": {"type": "string"},
                        "to_address": {"type": "string"},
                        "amount": {"type": "number"},
                        "private_key": {"type": "string", "description": "Private key for signing"}
                    },
                    "required": ["from_address", "to_address", "amount", "private_key"]
                }
            },
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            }
        },
        "tags": [
            {"name": "Blockchain", "description": "Blockchain and block operations"},
            {"name": "Transactions", "description": "Transaction management"},
            {"name": "Wallet", "description": "Wallet and balance operations"},
            {"name": "Mining", "description": "Block mining operations"},
            {"name": "Network", "description": "Network and peer management"}
        ]
    }

    return jsonify(openapi_spec)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
