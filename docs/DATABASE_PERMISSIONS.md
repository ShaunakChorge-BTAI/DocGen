# Database Permissions & Dependencies Guide

This guide details all prerequisites, driver installations, server configurations, and database privileges required to scan and monitor various database engines using DBAnalyser.

---

## 1. PostgreSQL Setup & Permissions

### Python Dependencies
Defined in [requirements.txt](file:///d:/Library/Documents/Projects/Internship/DB_Analyser/requirements.txt):
* `psycopg2-binary>=2.9.0` (standard driver) or compile from source using `psycopg2`.

### Database Privileges
To execute metadata queries and basic table/index scanning, the user requires read access to standard catalog views (`pg_class`, `pg_namespace`, etc.).
To execute **Live Monitor** metrics (active sessions, blocking locks, etc.) as a non-superuser:
* **`pg_monitor` role membership** (PostgreSQL 10+) is highly recommended. Without it, the user can only see their own active queries in `pg_stat_activity`, and details for other queries will display as `<insufficient privilege>` or remain hidden.
* Execute the following as a superuser (`postgres`):
  ```sql
  GRANT pg_monitor TO dbanalyser_user;
  ```

### PostgreSQL Slow Query Tracking (`pg_stat_statements`)
Slow queries in PostgreSQL are fetched using the `pg_stat_statements` system catalog view. This extension runs inside the database engine and **cannot** be installed via python `requirements.txt` or `pip`. 

Follow these steps to enable it on your PostgreSQL server:

1. **Locate your `postgresql.conf` file**:
   In your SQL console, execute:
   ```sql
   SHOW config_file;
   ```
2. **Enable the Shared Preload Library**:
   Open `postgresql.conf` in a text editor, search for `shared_preload_libraries`, and add `pg_stat_statements` to it (comma-separated):
   ```ini
   shared_preload_libraries = 'pg_stat_statements'
   ```
   *Note: If other libraries are listed, keep them and append `pg_stat_statements`.*
3. **Configure Additional Settings (Optional)**:
   Below the preload library, you can configure how queries are tracked:
   ```ini
   pg_stat_statements.max = 10000
   pg_stat_statements.track = all
   ```
4. **Restart PostgreSQL Service**:
   Apply changes by restarting the PostgreSQL service (e.g. via Windows Services, `pg_ctl restart`, or docker restart).
5. **Create the Extension**:
   Connect to the specific target database you want to monitor and run:
   ```sql
   CREATE EXTENSION pg_stat_statements;
   ```
6. **Verify Installation**:
   Ensure the view is accessible and returning results:
   ```sql
   SELECT * FROM pg_stat_statements LIMIT 5;
   ```

---

## 2. Microsoft SQL Server (MSSQL) Setup & Permissions

### Python Dependencies
Defined in [requirements.txt](file:///d:/Library/Documents/Projects/Internship/DB_Analyser/requirements.txt):
* `pyodbc>=5.0.0` (recommended for Windows/ODBC setup) or `pymssql>=2.2.0`.

### OS Prerequisite Drivers
* **Microsoft ODBC Driver for SQL Server**: Version 17 or 18 must be installed on the system hosting the DBAnalyser backend API server.
* Download links: [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).

### Database Privileges
To extract schema metadata, the connection account must belong to the database role `db_datareader`.
To use **Live Monitoring** and retrieve query performance statistics, wait stats, blocking session chains, and missing index suggestions from Dynamic Management Views (DMVs):
* **Server State View Permission**: Requires server-level view privileges to access views like `sys.dm_exec_query_stats`, `sys.dm_os_wait_stats`, etc.
* **Database State View Permission**: Requires database-level view privileges for `sys.dm_db_index_usage_stats` and `sys.dm_db_missing_index_details`.
* Run these scripts as an administrator (`sa`):
  ```sql
  -- Grant server level view privileges
  USE master;
  GRANT VIEW SERVER STATE TO [dbanalyser_user];
  -- (Optional for SQL Server 2022+)
  -- GRANT VIEW SERVER PERFORMANCE STATE TO [dbanalyser_user];

  -- Grant database level view privileges on your specific application DB
  USE [YourDatabaseName];
  GRANT VIEW DATABASE STATE TO [dbanalyser_user];
  ```

---

## 3. MySQL Setup & Permissions

### Python Dependencies
Defined in [requirements.txt](file:///d:/Library/Documents/Projects/Internship/DB_Analyser/requirements.txt):
* `mysql-connector-python>=8.0.0` or `PyMySQL`.

### Database Privileges
To extract schema structures, standard select permissions on target schemas and the `information_schema` database are sufficient.
To enable **Live Monitoring** (index scans, slow query digests, wait states):
1. **Enable Performance Schema**:
   Ensure `performance_schema` is turned on in your MySQL configuration (`my.cnf` / `my.ini`):
   ```ini
   performance_schema = ON
   ```
2. **Grant Select Privileges**:
   The analyzer queries performance tables and system helper views:
   ```sql
   GRANT SELECT ON performance_schema.* TO 'dbanalyser_user'@'%';
   GRANT SELECT ON sys.* TO 'dbanalyser_user'@'%';
   ```
3. **Grant Process Privilege**:
   Required to view blocking sessions and other user connection states in `information_schema.processlist`:
   ```sql
   GRANT PROCESS ON *.* TO 'dbanalyser_user'@'%';
   ```

---

## 4. Oracle Database Setup & Permissions

### Python Dependencies
Defined in [requirements.txt](file:///d:/Library/Documents/Projects/Internship/DB_Analyser/requirements.txt):
* `oracledb>=2.0.0` (standard python-oracledb Thin/Thick client).

### Database Privileges
To extract schema metadata, the user must have read privileges on the dictionary catalog views (`DBA_TABLES`, `DBA_INDEXES`, `DBA_TAB_COLS`, `DBA_SEGMENTS`).
* **Catalog Role**: The easiest way is to grant the catalog select role:
  ```sql
  GRANT SELECT_CATALOG_ROLE TO dbanalyser_user;
  ```
To retrieve **Live Monitor** metrics (active sessions, blocking status, system wait events) from Dynamic Performance Views (V$ views):
* The database user must be explicitly granted select privileges on the underlying v_$ views:
  ```sql
  GRANT SELECT ON V_$SESSION TO dbanalyser_user;
  GRANT SELECT ON V_$SQL TO dbanalyser_user;
  GRANT SELECT ON V_$SESSION_WAIT TO dbanalyser_user;
  GRANT SELECT ON V_$SYSTEM_EVENT TO dbanalyser_user;
  ```

---

## 5. Snowflake Setup & Permissions

### Python Dependencies
Defined in [requirements.txt](file:///d:/Library/Documents/Projects/Internship/DB_Analyser/requirements.txt):
* `snowflake-connector-python>=3.0.0`.

### Database Privileges
Snowflake metrics (slow queries, table storage metrics) are fetched from the shared system `SNOWFLAKE` database inside `ACCOUNT_USAGE` schema.
1. **Grant Imported Privileges**:
   Provide the role assigned to the DBAnalyser user access to Snowflake account metadata:
   ```sql
   GRANT IMPORTED PRIVILEGES ON DATABASE snowflake TO ROLE dbanalyser_role;
   ```
2. **Grant Target Database usage**:
   The role must also be able to navigate to and query the databases being analyzed:
   ```sql
   GRANT USAGE ON DATABASE <database_name> TO ROLE dbanalyser_role;
   GRANT USAGE ON SCHEMA <database_name>.<schema_name> TO ROLE dbanalyser_role;
   GRANT SELECT ON ALL TABLES IN SCHEMA <database_name>.<schema_name> TO ROLE dbanalyser_role;
   ```
