"""
Simple Oracle connection checker.

Usage:
  - Install 'oracledb' Python package (thin mode) or 'cx_Oracle'.
    Recommended: pip install oracledb

  - Run with environment variables or pass arguments:

    SET ORACLE_HOST=172.24.60.136
    SET ORACLE_PORT=1521
    SET ORACLE_SERVICE=DEVUAT_PDB1
    SET ORACLE_USER=INT_UAT_ZENX_LICENSE
    SET ORACLE_PASSWORD=int_UAT_Zenx_LICENSE$25#

    python simple_oracle_check.py

Or pass on the command line:
    python simple_oracle_check.py --host 172.24.60.136 --port 1521 --service DEVUAT_PDB1 --user ... --password ...

The script attempts a simple connection and runs a lightweight query.
"""
import os
import argparse
import sys

try:
    import oracledb
except Exception:
    print("Package 'oracledb' not installed. Install with: pip install oracledb")
    sys.exit(1)


def build_dsn(host, port, service=None, sid=None):
    if service:
        return f"{host}:{port}/{service}"
    if sid:
        return f"{host}:{port}/{sid}"
    return f"{host}:{port}"


def main():
    p = argparse.ArgumentParser(description="Simple Oracle connection checker")
    p.add_argument("--host", '172.24.60.136')
    p.add_argument("--port",  1521)
    p.add_argument("--service", "DEVUAT_PDB1")
    # p.add_argument("--sid", "ORACLE_SID"
    p.add_argument("--user", "INT_UAT_ZENX_LICENSE")
    p.add_argument("--password", "INT_UAT_ZENX_LICENSE")
    # p.add_argument("--connect-as","ORACLE_CONNECT_AS", None)

    args = p.parse_args()

    dsn = build_dsn(args.host, args.port, service=args.service, sid=args.sid)

    print(f"Attempting to connect to Oracle at {dsn} as user='{args.user}'")

    try:
        # Thin mode connect (no Oracle client binaries required)
        conn_kwargs = {"user": args.user, "password": args.password, "dsn": dsn}
        if args.connect_as == "sysdba":
            conn_kwargs["mode"] = oracledb.AUTH_MODE_SYSDBA

        conn = oracledb.connect(**conn_kwargs)
        print("Connection successful.")
        cur = conn.cursor()
        cur.execute("SELECT sysdate FROM dual")
        row = cur.fetchone()
        print("Test query result:", row)
        cur.close()
        conn.close()
        return 0
    except Exception as e:
        print("Connection failed:", e)
        return 2


if __name__ == "__main__":
    """Minimal Oracle connection checker with hardcoded settings."""
    import sys
    import traceback

    try:
        import oracledb
    except Exception:
        print("Package 'oracledb' not installed. Install with: pip install oracledb")
        sys.exit(1)

    # Hardcoded connection settings - edit as needed
    HOST = "172.24.60.136"
    PORT = 1521
    SERVICE = "DEVUAT_PDB1"  # or SID value
    USER = "INT_UAT_ZENX_LICENSE"
    PASSWORD = "int_UAT_Zenx_LICENSE$25#"
    CONNECT_AS_SYSDBA = False

    def build_dsn(host, port, service=None):
        if service:
            return f"{host}:{port}/{service}"
        return f"{host}:{port}"

    def main():
        dsn = build_dsn(HOST, PORT, service=SERVICE)
        print(f"Attempting to connect to Oracle at {dsn} as user='{USER}'")
        try:
            conn_kwargs = {"user": USER, "password": PASSWORD, "dsn": dsn}
            if CONNECT_AS_SYSDBA:
                conn_kwargs["mode"] = oracledb.AUTH_MODE_SYSDBA

            conn = oracledb.connect(**conn_kwargs)
            print("Connection successful.")
            cur = conn.cursor()
            cur.execute("SELECT sysdate FROM dual")
            row = cur.fetchone()
            print("Test query result:", row)
            cur.close()
            conn.close()
            return 0
        except Exception:
            print("Connection failed.")
            traceback.print_exc()
            return 2

    if __name__ == "__main__":
        sys.exit(main())
