import argparse
import yaml
import os
import sys

from .migrate_data import migrate_data
from .constraints import add_primary_keys, add_foreign_keys


TEMPLATE_CONFIG = """\
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

mode: strict
batch_size: 1000
"""


def create_template_config():
    if os.path.exists("migration.yaml"):
        print("migration.yaml already exists. Aborting.")
        return

    with open("migration.yaml", "w") as f:
        f.write(TEMPLATE_CONFIG)

    print("migration.yaml template created successfully.")
    print("Edit the file before running migration.")


def main():
    parser = argparse.ArgumentParser(
        description="MSSQL to MySQL Migration Tool"
    )

    parser.add_argument(
        "--config",
        help="Path to migration config file"
    )

    parser.add_argument(
        "--init",
        action="store_true",
        help="Create a sample migration.yaml file"
    )

    args = parser.parse_args()

    if args.init:
        create_template_config()
        return

    if not args.config:
        print("Error: Please provide --config <file>")
        sys.exit(1)

    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    mssql_config = {
        "DRIVER": "{ODBC Driver 18 for SQL Server}",
        "SERVER": f"{config['mssql']['server']},{config['mssql']['port']}",
        "DATABASE": config["mssql"]["database"],
        "UID": config["mssql"]["user"],
        "PWD": config["mssql"]["password"],
        "TrustServerCertificate": "yes",
    }

    mysql_config = {
        "host": config["mysql"]["host"],
        "database": config["mysql"]["database"],
        "user": config["mysql"]["user"],
        "password": config["mysql"]["password"],
    }

    mode = config.get("mode", "strict")
    batch_size = config.get("batch_size", 1000)

    migrate_data(mssql_config, mysql_config, batch_size=batch_size)
    add_primary_keys(mssql_config, mysql_config)
    add_foreign_keys(mssql_config, mysql_config, mode=mode)

    print("Migration finished successfully.")


if __name__ == "__main__":
    main()
