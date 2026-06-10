import sys

try:
    import oracledb
except ImportError:
    print("Error: oracledb package not installed. Run 'pip install oracledb' first.")
    sys.exit(1)

def test_connection(host, port, service_or_sid, user, password, is_sid=False):
    print(f"Testing connection to {host}:{port} with {'SID' if is_sid else 'Service Name'} '{service_or_sid}'...")
    try:
        if is_sid:
            # Using makedsn for SID
            dsn = oracledb.makedsn(host, port, sid=service_or_sid)
            conn = oracledb.connect(user=user, password=password, dsn=dsn)
        else:
            # Using Easy Connect string for Service Name
            dsn = f"{host}:{port}/{service_or_sid}"
            conn = oracledb.connect(user=user, password=password, dsn=dsn)
        
        print("Connection successful!")
        print(f"Database Version: {conn.version}")
        conn.close()
        return True
    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"Connection failed. Error code: {error.code}")
        print(f"Message: {error.message}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("=== Oracle DB Connection Tester ===")
    
    # Defaults
    host = "localhost"
    port = "1521"
    service_name = "XEPDB1" # Default for newer Oracle XE pluggable DBs
    sid = "XE" # Default SID for older Oracle XE
    user = "system"
    password = "OraclePassword123"

    print("\nPlease update the variables in this script to match your work PC's Oracle database credentials before running.\n")
    
    print("--- Test 1: Connecting using Service Name ---")
    test_connection(host, port, service_name, user, password, is_sid=False)
    
    print("\n--- Test 2: Connecting using SID ---")
    test_connection(host, port, sid, user, password, is_sid=True)
