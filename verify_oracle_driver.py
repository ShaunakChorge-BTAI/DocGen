import logging
from dbanalyser.config import load_config
from dbanalyser.db.driver_factory import get_driver
import os

logging.basicConfig(level=logging.INFO)

def main():
    # Merged connection parameters and credential candidates from mixed configs
    base_conn = {
        "type": "oracle",
        "name": "DEVUAT_PDB1",
        # prefer IP if available; fallback to localhost
        "host": "172.24.60.136",
        "port": 1521,
        # TNS / service alias
        "tns_name": "DEVUAT_PDB1",
        # possible SIDs/services
        "sid": "xe",
        "service": "DEVUAT_PDB1",
    }

    # Credential candidates to try (order matters)
    credentials = [
        {"username": "INT_UAT_ZENX_LICENSE", "password": "int_UAT_Zenx_LICENSE$25#"},
        {"username": "OP_ALKEM_ML", "password": "wM2FHmc#qZ$mHqH$1"},
    ]

    config = load_config()
    db_entry = None
    try:
        db_entry = config.get_database("LOCAL_ORACLE_XE")
    except Exception:
        db_entry = None

    # Log the config entry (masked) if present
    if db_entry:
        try:
            cfg_dict = {k: getattr(db_entry, k) for k in dir(db_entry) if not k.startswith("__") and not callable(getattr(db_entry, k))}
        except Exception:
            cfg_dict = {}
        masked = cfg_dict.copy()
        if "password" in masked:
            masked["password"] = "*****"
        logging.info("Config entry from file (masked): %s", masked)

    if not db_entry:
        from types import SimpleNamespace
        db_entry = None
        driver = None

        # Try each credential until one succeeds
        for cred in credentials:
            payload = {**base_conn, **cred}
            # Some drivers expect fields like .username/.password or .user
            if "username" in payload and "user" not in payload:
                payload["user"] = payload["username"]

            # Log the payload with masked password; optionally log unmasked if env var set
            logged = payload.copy()
            if "password" in logged:
                logged["password"] = "*****"
            logging.info("Attempting payload (masked): %s", logged)
            if os.getenv("UNMASK_PAYLOADS") == "1":
                logging.warning("Attempting payload (UNMASKED): %s", payload)

            candidate = SimpleNamespace(**payload)
            print(f"Trying to connect as {candidate.user}@{candidate.host}:{candidate.port} (tns={candidate.tns_name})...")
            try:
                driver = get_driver(candidate)
                if driver.test_connection():
                    print(f"Connection Test: PASSED (user={candidate.user})")
                    db_entry = candidate
                    break
                else:
                    print(f"Connection failed for user={candidate.user}")
            except Exception as e:
                print(f"Attempt error for user={candidate.user}: {e}")

        if not db_entry:
            print("All credential attempts failed; aborting.")
            return
    else:
        print(f"Connecting to {db_entry.name}...")
        driver = get_driver(db_entry)
        if not driver.test_connection():
            print("Connection Test: FAILED for config entry from config file.")
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
