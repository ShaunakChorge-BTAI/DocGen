"""
Unit tests for the file-based scanner.

Run with:
    cd D:\\LTFS\\ltfs-analyzer
    python -m pytest tests/test_scanner.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dbanalyser.engine.scanner import scan_files, _guess_type_from_source, _extract_object_name

FIXTURES = Path(__file__).parent / "fixtures"


class TestGuessTypeFromSource:
    def test_detects_stored_procedure(self):
        src = "CREATE OR ALTER PROCEDURE dbo.MyProc AS BEGIN SELECT 1 END"
        assert _guess_type_from_source(src, "myproc.sql") == "Stored Procedure"

    def test_detects_view(self):
        src = "CREATE VIEW dbo.MyView AS SELECT 1 AS Col"
        assert _guess_type_from_source(src, "myview.sql") == "View"

    def test_detects_trigger(self):
        src = "CREATE TRIGGER dbo.trg_Audit ON dbo.Orders AFTER INSERT AS SELECT 1"
        assert _guess_type_from_source(src, "trg.sql") == "Trigger"

    def test_detects_table(self):
        src = "CREATE TABLE dbo.MyTable (Id INT NOT NULL)"
        assert _guess_type_from_source(src, "table.sql") == "Table"

    def test_falls_back_to_filename(self):
        src = "-- no create statement"
        assert _guess_type_from_source(src, "sp_legacy.sql") == "Stored Procedure"


class TestExtractObjectName:
    def test_extracts_schema_and_name(self):
        src = "CREATE PROCEDURE dbo.GetOrders AS SELECT 1"
        schema, name = _extract_object_name(src, "file.sql")
        assert schema == "dbo"
        assert name == "GetOrders"

    def test_defaults_to_dbo_schema(self):
        src = "CREATE PROCEDURE GetOrders AS SELECT 1"
        schema, name = _extract_object_name(src, "file.sql")
        assert schema == "dbo"
        assert name == "GetOrders"

    def test_falls_back_to_filename(self):
        src = "-- no DDL"
        schema, name = _extract_object_name(src, "usp_MyProc.sql")
        assert name == "usp_MyProc"


class TestScanFiles:
    def test_scans_fixture_directory(self):
        objects = list(scan_files(str(FIXTURES)))
        assert len(objects) >= 2, "Should find at least good_proc and bad_proc fixtures"

    def test_yields_sql_objects_with_source(self):
        objects = list(scan_files(str(FIXTURES)))
        for obj in objects:
            assert obj.source != "", f"{obj.name} has empty source"
            assert obj.obj_type != "", f"{obj.name} has empty obj_type"

    def test_filter_by_type(self):
        objects = list(scan_files(str(FIXTURES), include_types=["Stored Procedure"]))
        for obj in objects:
            assert obj.obj_type == "Stored Procedure", \
                f"Expected Stored Procedure, got {obj.obj_type} for {obj.name}"

    def test_nonexistent_directory_raises(self):
        with pytest.raises(FileNotFoundError):
            list(scan_files("C:/does/not/exist"))

    def test_source_lines_populated(self):
        objects = list(scan_files(str(FIXTURES)))
        for obj in objects:
            assert len(obj.source_lines) > 0

    def test_source_upper_populated(self):
        objects = list(scan_files(str(FIXTURES)))
        for obj in objects:
            assert obj.source_upper == obj.source.upper()
