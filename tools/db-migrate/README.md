# RustChain Database Migration Tool

Versioned, reversible schema migration runner for the RustChain SQLite database.

## Quick Start

```bash
# Show current migration status
python tools/db-migrate/migrate.py status

# Apply all pending migrations
python tools/db-migrate/migrate.py up

# Roll back the last applied migration
python tools/db-migrate/migrate.py down
```

## Commands

| Command | Description |
|---------|-------------|
| `up` | Apply all pending migrations in version order |
| `down` | Roll back the single most-recent migration |
| `status` | List every migration and whether it has been applied |
| `create NAME` | Scaffold a new empty migration file |

### Options

```
--db PATH    Path to the SQLite database
             Default: $RUSTCHAIN_DB_PATH or ./rustchain_v2.db

--dir PATH   Path to the migrations/ directory
             Default: tools/db-migrate/migrations/
```

## Writing Migrations

Each migration is a single `.sql` file inside `migrations/` with the naming
convention:

```
V{version}__{description}.sql
```

The file must contain two clearly marked sections:

```sql
-- UP
CREATE TABLE foo (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS foo;
```

- **UP** — forward (apply) SQL.
- **DOWN** — rollback SQL that cleanly reverses the UP block.

### Creating a new migration

```bash
python tools/db-migrate/migrate.py create "add staking rewards table"
# Creates migrations/V0021__add_staking_rewards_table.sql
```

Edit the generated file and fill in the UP / DOWN blocks.

## How It Works

The runner stores applied-migration state in a `_migrations` table inside the
target database.  Each row records the version string, a human-readable name,
the unix timestamp when it was applied, and a checksum of the UP SQL so that
`migrate status` can flag files that were modified after being applied.

Migrations are executed inside a transaction so a failure leaves the database
unchanged.

## Included Migrations

| Version | Description |
|---------|-------------|
| V0018 | Baseline schema — records the full v2.2.1 table set |
| V0019 | Add miner uptime tracking table |
| V0020 | Add peer reputation table |

## Integration with the Node

The node's `init_db()` uses `CREATE TABLE IF NOT EXISTS` statements, so
running migrations alongside the node is safe — both paths are idempotent.
The migration tool simply provides a structured, auditable way to evolve
the schema over time and roll back if needed.
