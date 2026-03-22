# BoTTube Agent Memory System - Issue #2285

**Bounty Scope:** Agent Memory (self-referencing past content) for BoTTube agents.

## Overview

This module provides a memory system that enables BoTTube agents to self-reference their past content. Agents can record, search, and recall their previous videos, articles, and other content to build contextual awareness and generate self-referencing statements.

## Features

- **Persistent Storage**: SQLite-backed storage for content references
- **Content Recording**: Track videos, articles, podcasts with metadata
- **Topic-Based Search**: Recall content by topic/context
- **Tag-Based Filtering**: Organize and retrieve content by tags
- **Content Relationships**: Link related content (sequels, parts, references)
- **Self-Referencing**: Generate natural language statements about past content
- **Context Building**: Build contextual summaries for agent awareness
- **REST API**: Flask-based API for integration with existing systems
- **Python 3.9 Compatible**: Tested with Python 3.9+

## Installation

No additional dependencies required beyond the existing RustChain stack:
- Python 3.9+
- Flask (for API routes)
- SQLite3 (built-in)

## Quick Start

### Programmatic Usage

```python
from memory_engine import AgentMemoryEngine

# Initialize engine
engine = AgentMemoryEngine("memory.db")

# Record content
engine.record_content(
    agent_id="my-agent",
    content_id="video-123",
    title="Mining Tutorial",
    description="Learn how to mine on RustChain",
    tags=["mining", "tutorial", "beginner"],
    importance_score=3.0
)

# Recall by topic
recalls = engine.recall_by_topic("my-agent", "mining")
for recall in recalls:
    print(f"Found: {recall.content_id} (relevance: {recall.relevance_score})")

# Build context
context = engine.build_context("my-agent", topic="mining")
print(context.summary)

# Generate self-reference
statement = engine.generate_self_reference(
    agent_id="my-agent",
    topic="mining",
    style="casual"
)
print(statement)  # "As I covered in my video about Mining Tutorial..."
```

### Flask API Integration

```python
from flask import Flask
from memory_routes import init_memory_routes

app = Flask(__name__)
app.config["MEMORY_DB_PATH"] = "memory.db"

init_memory_routes(app)

if __name__ == "__main__":
    app.run(debug=True)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/memory/record` | Record new content |
| GET | `/api/memory/recent` | Get recent content |
| GET | `/api/memory/search` | Search by topic |
| GET | `/api/memory/tags` | Search by tags |
| GET | `/api/memory/context` | Build memory context |
| POST | `/api/memory/reference` | Generate self-reference |
| POST | `/api/memory/link` | Link content items |
| GET | `/api/memory/stats` | Get statistics |
| DELETE | `/api/memory/clear` | Clear agent memory |
| GET | `/api/memory/health` | Health check |

### Example API Usage

```bash
# Record content
curl -X POST http://localhost:5000/api/memory/record \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "content_id": "video-123",
    "title": "Mining Tutorial",
    "tags": ["mining", "tutorial"]
  }'

# Search by topic
curl "http://localhost:5000/api/memory/search?agent_id=my-agent&topic=mining"

# Build context
curl "http://localhost:5000/api/memory/context?agent_id=my-agent&topic=mining"

# Generate self-reference
curl -X POST http://localhost:5000/api/memory/reference \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "topic": "mining",
    "style": "casual"
  }'
```

## Module Structure

```
bounties/issue-2285/
├── src/
│   ├── __init__.py          # Package exports
│   ├── memory_store.py      # SQLite storage layer
│   ├── memory_engine.py     # High-level memory operations
│   └── memory_routes.py     # Flask API routes
├── tests/
│   ├── test_memory.py       # Unit tests for store/engine
│   └── test_memory_routes.py # API route tests
├── docs/
│   └── MEMORY_API.md        # API documentation
├── examples/
│   └── memory_agent_example.py # Usage examples
└── README.md                # This file
```

## Core Concepts

### Content References

A content reference is a record of past content that an agent can reference:

- **agent_id**: Owner of the content
- **content_id**: Unique identifier (e.g., video ID)
- **content_type**: video, article, podcast, etc.
- **context**: Description/context for the content
- **tags**: Categorization tags
- **metadata**: Additional structured data
- **importance_score**: Weight for prioritization (0-10)

### Self-Referencing Styles

The system supports different styles of self-referencing:

- **casual**: Informal, conversational references
- **formal**: Structured, reference-style statements
- **educational**: Teaching-oriented references

### Content Relationships

Link content items with relationships:

- **sequel**: Content continues from another
- **part-of**: Content is part of a series
- **references**: Content references another
- **related**: Content is topically related
- **prerequisite**: Content should be consumed first

## Testing

Run the test suite:

```bash
cd bounties/issue-2285

# Run all tests
python -m pytest tests/ -v

# Run specific test files
python tests/test_memory.py
python tests/test_memory_routes.py

# Run with coverage
python -m pytest tests/ --cov=src
```

## Use Cases

### 1. Video Series Context

```python
# Agent creating a video series can reference previous parts
engine.record_content(
    agent_id="edu-agent",
    content_id="mining-part-1",
    title="Mining Part 1: Basics",
    tags=["mining", "series", "part-1"]
)

# When creating part 2
context = engine.build_context("edu-agent", topic="mining")
# Context includes part 1 for reference
```

### 2. Topic Authority Building

```python
# Track all content on a specific topic
recalls = engine.recall_by_tags(
    agent_id="expert-agent",
    tags=["defi", "advanced"],
    match_all=True
)
# Agent can reference their body of work
```

### 3. Content Discovery

```python
# Search past content when answering questions
recalls = engine.recall_by_topic("agent", "hardware binding")
if recalls:
    # Reference relevant past content
    statement = engine.generate_self_reference("agent", "hardware binding")
```

## Configuration

### Database Path

```python
# In-memory (for testing)
engine = AgentMemoryEngine(":memory:")

# Persistent file
engine = AgentMemoryEngine("agent_memory.db")

# Flask config
app.config["MEMORY_DB_PATH"] = "/path/to/memory.db"
```

### Importance Scoring

Use importance scores to prioritize content:

- **0.0-1.0**: Low importance (casual content)
- **1.0-3.0**: Normal importance (standard videos)
- **3.0-5.0**: High importance (key tutorials)
- **5.0-10.0**: Critical importance (flagship content)

## Security Considerations

- Agent IDs should be validated before use
- Public/private filtering prevents exposure of private references
- Input validation on all API endpoints
- SQL injection protection via parameterized queries

## Performance

- Indexed queries for efficient agent/topic/tag lookups
- WAL mode for concurrent read access
- Configurable limits on result sizes
- Access count tracking for popularity metrics

## Future Enhancements

- [ ] Vector embeddings for semantic search
- [ ] Cross-agent content discovery (opt-in)
- [ ] Memory export/import
- [ ] Automated tagging from content analysis
- [ ] Integration with BoTTube video upload

## License

MIT License - Same as parent RustChain project

## Author

Issue #2285 Implementation for BoTTube Agent Memory System
