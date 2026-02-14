import pyodbc
import mysql.connector
import logging
from contextlib import closing


def print_progress(table, current, total, bar_length=30):
    if total == 0:
        percent = 100
        filled_length = bar_length
    else:
        percent = int((current / total) * 100)
        filled_length = int(bar_length * current // total)

    bar = "=" * filled_length + ">" + " " * (bar_length - filled_length - 1)

    print(
        f"\rMigrating table: {table}  [{bar}] {percent}% ({current}/{total})",
        end="",
        flush=True,
    )


def map_mssql_to_mysql(dtype, char_len, num_precision, num_scale, is_nullable):
    dtype = dtype.lower()

    if dtype in ("varbinary", "binary", "image"):
        mysql_type = "LONGBLOB" if char_len == -1 else "BLOB"

    elif dtype in ("varchar", "nvarchar", "char", "nchar"):
        mysql_type = "LONGTEXT" if char_len == -1 else f"VARCHAR({char_len})"

    elif dtype in ("decimal", "numeric"):
        mysql_type = f"DECIMAL({num_precision},{num_scale})"

    elif dtype == "bit":
        mysql_type = "TINYINT(1)"

    elif dtype in ("datetime", "datetime2"):
        mysql_type = "DATETIME"

    elif dtype == "date":
        mysql_type = "DATE"

    elif dtype == "int":
        mysql_type = "INT"

    elif dtype == "bigint":
        mysql_type = "BIGINT"

    else:
        mysql_type = "TEXT"

    if is_nullable == "NO":
        mysql_type += " NOT NULL"

    return mysql_type


def migrate_data(mssql_config: dict, mysql_config: dict, batch_size: int = 1000):
    logging.info("Starting data migration...")

    with closing(pyodbc.connect(**mssql_config)) as mssql_conn, closing(
        mysql.connector.connect(**mysql_config)
    ) as mysql_conn:

        mssql_cursor = mssql_conn.cursor()
        mysql_cursor = mysql_conn.cursor()

        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=0;")

        mssql_cursor.execute(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE='BASE TABLE'
        """
        )

        tables = [row[0] for row in mssql_cursor.fetchall()]
        total_tables = len(tables)

        for index, table in enumerate(tables, start=1):
            print(f"\n🔹 [{index}/{total_tables}] Starting table: {table}")

            mssql_cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE,
                       CHARACTER_MAXIMUM_LENGTH,
                       NUMERIC_PRECISION,
                       NUMERIC_SCALE,
                       IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
            """,
                table,
            )

            columns = mssql_cursor.fetchall()

            if not columns:
                print(f"⚠ No columns found for {table}, skipping.")
                continue

            column_defs = []
            column_names = []

            for col, dtype, char_len, num_precision, num_scale, is_nullable in columns:
                mysql_type = map_mssql_to_mysql(
                    dtype, char_len, num_precision, num_scale, is_nullable
                )
                column_defs.append(f"`{col}` {mysql_type}")
                column_names.append(col)

            create_sql = f"""
                CREATE TABLE IF NOT EXISTS `{table}` (
                    {", ".join(column_defs)}
                )
            """
            mysql_cursor.execute(create_sql)
            mysql_conn.commit()

            mssql_cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
            total_rows = mssql_cursor.fetchone()[0]

            if total_rows == 0:
                print(f"✔ Completed {table} (0 rows)")
                continue

            # Start Data Migration
            escaped_columns = ", ".join(f"[{c[0]}]" for c in columns)
            select_sql = f"SELECT {escaped_columns} FROM [{table}]"
            mssql_cursor.execute(select_sql)

            insert_columns = ", ".join(f"`{c}`" for c in column_names)
            placeholders = ", ".join(["%s"] * len(column_names))
            insert_sql = f"""
                INSERT INTO `{table}` ({insert_columns})
                VALUES ({placeholders})
            """

            total_inserted = 0

            while True:
                batch = mssql_cursor.fetchmany(batch_size)
                if not batch:
                    break

                clean_rows = [
                    tuple(int(v) if isinstance(v, bool) else v for v in row)
                    for row in batch
                ]

                try:
                    mysql_cursor.executemany(insert_sql, clean_rows)
                    mysql_conn.commit()
                    total_inserted += len(clean_rows)

                    print_progress(table, total_inserted, total_rows)

                except mysql.connector.Error as e:
                    logging.error(f"Batch failed in table {table}: {e}")
                    mysql_conn.rollback()

            print()
            print(f"✔ Completed {table} ({total_inserted} rows inserted)")

        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=1;")

    print("\nTabel migration completed successfully.")
