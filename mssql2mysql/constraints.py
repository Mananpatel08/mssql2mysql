import pyodbc
import mysql.connector
import logging
from contextlib import closing


def add_primary_keys(mssql_config: dict, mysql_config: dict):
    print("\nStarting Primary Key migration...\n")

    with closing(pyodbc.connect(**mssql_config)) as mssql_conn, closing(
        mysql.connector.connect(**mysql_config)
    ) as mysql_conn:

        mssql_cursor = mssql_conn.cursor()
        mysql_cursor = mysql_conn.cursor()

        # Fetch PK metadata from MSSQL
        mssql_cursor.execute(
            """
            SELECT
                tc.TABLE_NAME,
                kc.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kc
                ON tc.CONSTRAINT_NAME = kc.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY tc.TABLE_NAME, kc.ORDINAL_POSITION
        """
        )

        pk_map = {}
        for table, column in mssql_cursor.fetchall():
            pk_map.setdefault(table, []).append(column)

        total_tables = len(pk_map)

        for index, (table, columns) in enumerate(pk_map.items(), start=1):
            cols = ", ".join(f"`{c}`" for c in columns)

            print(f"🔹 [{index}/{total_tables}] Adding PK for table: {table}")

            try:
                # Check if PK already exists
                mysql_cursor.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM information_schema.TABLE_CONSTRAINTS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = %s
                      AND CONSTRAINT_TYPE = 'PRIMARY KEY'
                """,
                    (table,),
                )

                exists = mysql_cursor.fetchone()[0]

                if exists:
                    print(f"   ⚠ Primary key already exists for {table}, skipping.")
                    continue

                sql = f"ALTER TABLE `{table}` ADD PRIMARY KEY ({cols})"
                mysql_cursor.execute(sql)
                mysql_conn.commit()

                print(f"   ✔ PK added ({cols})")

            except mysql.connector.Error as e:
                mysql_conn.rollback()
                logging.error(f"PK failed for {table}: {e}")
                print(f"[ERROR] PK failed for {table}")

    print("\nPrimary key migration finished.\n")


def add_foreign_keys(
    mssql_config: dict,
    mysql_config: dict,
    mode: str = "strict",
):
    print(f"\nStarting Foreign Key migration (mode={mode})...\n")

    with closing(pyodbc.connect(**mssql_config)) as mssql_conn, closing(
        mysql.connector.connect(**mysql_config)
    ) as mysql_conn:

        mssql_cursor = mssql_conn.cursor()
        mysql_cursor = mysql_conn.cursor()

        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=0;")

        mssql_cursor.execute(
            """
            SELECT
                fk.name,
                tp.name AS parent_table,
                cp.name AS parent_column,
                tr.name AS ref_table,
                cr.name AS ref_column
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc
                ON fk.object_id = fkc.constraint_object_id
            JOIN sys.tables tp
                ON fkc.parent_object_id = tp.object_id
            JOIN sys.columns cp
                ON cp.object_id = tp.object_id
               AND cp.column_id = fkc.parent_column_id
            JOIN sys.tables tr
                ON fkc.referenced_object_id = tr.object_id
            JOIN sys.columns cr
                ON cr.object_id = tr.object_id
               AND cr.column_id = fkc.referenced_column_id
            ORDER BY parent_table
            """
        )

        fks = mssql_cursor.fetchall()
        total_fks = len(fks)

        for index, (fk_name, table, column, ref_table, ref_column) in enumerate(
            fks, start=1
        ):

            print(
                f"🔹 [{index}/{total_fks}] Adding FK: {table}.{column} → {ref_table}.{ref_column}"
            )

            # Skip meaningless self PK-FK
            if table == ref_table and column == ref_column:
                print("   ⚠ Skipping redundant self PK-FK.")
                continue

            try:
                # Skip if FK already exists
                mysql_cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.TABLE_CONSTRAINTS
                    WHERE CONSTRAINT_SCHEMA = DATABASE()
                      AND TABLE_NAME = %s
                      AND CONSTRAINT_NAME = %s
                    """,
                    (table, fk_name),
                )

                if mysql_cursor.fetchone()[0]:
                    print("   ⚠ FK already exists, skipping.")
                    continue

                # ============================
                # SMART MODE LOGIC
                # ============================
                if mode == "smart":

                    # Ensure referenced column is indexed
                    mysql_cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.STATISTICS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s
                          AND COLUMN_NAME = %s
                        """,
                        (ref_table, ref_column),
                    )

                    if mysql_cursor.fetchone()[0] == 0:
                        print(
                            f"[SMART] Creating index on {ref_table}.{ref_column}"
                        )
                        mysql_cursor.execute(
                            f"ALTER TABLE `{ref_table}` "
                            f"ADD INDEX `idx_{ref_table}_{ref_column}` (`{ref_column}`)"
                        )
                        mysql_conn.commit()

                # ============================
                # ADD FK
                # ============================
                sql = f"""
                    ALTER TABLE `{table}`
                    ADD CONSTRAINT `{fk_name}`
                    FOREIGN KEY (`{column}`)
                    REFERENCES `{ref_table}`(`{ref_column}`)
                """

                mysql_cursor.execute(sql)
                mysql_conn.commit()

                print("   ✔ FK added successfully")

            except mysql.connector.Error as e:
                mysql_conn.rollback()

                if mode == "strict":
                    print("[ERROR] FK failed (strict mode stops here)")
                    raise  # stop migration in strict mode
                else:
                    print("[ERROR] FK failed (smart mode continues)")

        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS=1;")

    print("\nForeign key migration finished.\n")
