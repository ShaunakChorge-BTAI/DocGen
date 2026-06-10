import logging
from dbanalyser.config import load_config
from dbanalyser.db.driver_factory import get_driver

logging.basicConfig(level=logging.INFO)

def main():
    config = load_config()
    db_entry = config.get_database("LOCAL_ORACLE_XE")
    if not db_entry:
        print("Database 'LOCAL_ORACLE_XE' not found in config.")
        return

    print(f"Connecting to {db_entry.name}...")
    driver = get_driver(db_entry)
    
    if driver.test_connection():
        print("Connection Test: PASSED")
    else:
        print("Connection Test: FAILED")
        return

    print("Fetching tables...")
    try:
        tables = driver.list_tables()
        print(f"Found {len(tables)} tables. First 5:")
        for t in tables[:5]:
            print(f" - {t.schema}.{t.name}")
    except Exception as e:
        print(f"Failed to fetch tables: {e}")

    print("\nFetching views...")
    try:
        views = driver.list_views()
        print(f"Found {len(views)} views. First 5:")
        for v in views[:5]:
            print(f" - {v.schema}.{v.name}")
    except Exception as e:
        print(f"Failed to fetch views: {e}")

    print("\nFetching procedures...")
    try:
        procs = driver.list_procedures()
        print(f"Found {len(procs)} procedures. First 5:")
        for p in procs[:5]:
            print(f" - {p.schema}.{p.name}")
    except Exception as e:
        print(f"Failed to fetch procedures: {e}")

if __name__ == "__main__":
    main()
