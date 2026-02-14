# mssql2mysql

A config-driven CLI tool to migrate Microsoft SQL Server databases to MySQL. Handles data, primary keys, and foreign keys with batch processing and progress tracking.

## Features

- **Data migration** — Copies all tables and rows with configurable batch size
- **Schema inference** — Builds MySQL tables from MSSQL metadata with automatic type mapping
- **Primary keys** — Migrates PK constraints from MSSQL to MySQL
- **Foreign keys** — Migrates FK constraints with **strict** or **smart** mode
- **Progress tracking** — Per-table progress bars and row counts
- **YAML config** — Single config file for both source and target

## Requirements

- **Python** 3.9+
- **SQL Server ODBC Driver** (e.g. [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server))
- **MySQL Server** (target)

## Installation

```bash
pip install mssql2mysql
```

Or from source:

```bash
git clone https://github.com/mananpatel08/mssql2mysql.git
cd mssql2mysql
pip install -e .
```

## Quick Start

1. **Create a config file**

   ```bash
   mssql2mysql --init
   ```

   This creates `migration.yaml` in the current directory.

2. **Edit the config** with your MSSQL and MySQL connection details.

3. **Run the migration**

   ```bash
   mssql2mysql --config migration.yaml
   ```

## Configuration

Example `migration.yaml` (from `--init`):

```yaml
mssql:
  server: localhost
  port: 1433
  database: your_database
  user: sa
  password: your_password

mysql:
  host: localhost
  database: your_database
  user: root
  password: your_password

mode: strict      # strict | smart
batch_size: 1000
```

| Option        | Description |
|---------------|-------------|
| `mssql.server` | MSSQL host |
| `mssql.port`   | MSSQL port (default 1433) |
| `mssql.database` | Source database name |
| `mssql.user` / `mssql.password` | MSSQL credentials |
| `mysql.host`   | MySQL host |
| `mysql.database` | Target database name |
| `mysql.user` / `mysql.password` | MySQL credentials |
| `mode`         | `strict` (default): stop on first FK error. `smart`: create indexes on referenced columns if needed, continue on FK errors. |
| `batch_size`   | Rows per insert batch (default 1000) |

## CLI Reference

| Command | Description |
|---------|-------------|
| `mssql2mysql --init` | Create a sample `migration.yaml` in the current directory. |
| `mssql2mysql --config <file>` | Run migration using the given YAML config file. |

## Migration Modes

- **strict** (default) — Stops the entire migration if any foreign key fails to be added. Use when you want a fully consistent schema.
- **smart** — Before adding each FK, ensures the referenced column has an index (creates one if missing). On FK add failure, logs the error and continues with the rest. Use when some FKs may be invalid or you prefer best-effort migration.

## Type Mapping

MSSQL types are mapped to MySQL as follows (among others):

| MSSQL | MySQL |
|-------|--------|
| `varchar` / `nvarchar` / `char` / `nchar` | `VARCHAR(n)` or `LONGTEXT` (max) |
| `decimal` / `numeric` | `DECIMAL(p,s)` |
| `datetime` / `datetime2` | `DATETIME` |
| `date` | `DATE` |
| `int` | `INT` |
| `bigint` | `BIGINT` |
| `bit` | `TINYINT(1)` |
| `varbinary` / `binary` / `image` | `BLOB` / `LONGBLOB` |

Unsupported types fall back to `TEXT`. Nullability is preserved.

## How It Works

1. **Data** — Connects to MSSQL and MySQL, reads table list and column metadata, creates MySQL tables with mapped types, then batch-inserts rows with progress output. Foreign key checks are disabled during data load.
2. **Primary keys** — Reads PK definitions from MSSQL `INFORMATION_SCHEMA`, adds them in MySQL (skips if already present).
3. **Foreign keys** — Reads FK definitions from MSSQL system tables, adds them in MySQL (in **smart** mode, creates indexes on referenced columns as needed).

## Links

- **Repository:** [github.com/mananpatel08/mssql2mysql](https://github.com/mananpatel08/mssql2mysql)
- **Issues:** [github.com/mananpatel08/mssql2mysql/issues](https://github.com/mananpatel08/mssql2mysql/issues)

## License

MIT © [Manan Patel](https://github.com/mananpatel08)
