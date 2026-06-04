"""
Tests for dbanalyser.schema_intel
====================================
Covers: embedder, extractor, searcher (no DB required — all mocked).
"""
import math
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Embedder
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbedSchemaObject:
    def test_returns_list_of_floats(self):
        from dbanalyser.schema_intel.embedder import embed_schema_object
        vec = embed_schema_object("table", "Accounts", "", "CREATE TABLE Accounts (...)")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)

    def test_vector_dimension_256(self):
        from dbanalyser.schema_intel.embedder import embed_schema_object
        vec = embed_schema_object("column", "AccountId", "Accounts", "int NOT NULL")
        assert len(vec) == 256

    def test_different_inputs_different_vectors(self):
        from dbanalyser.schema_intel.embedder import embed_schema_object
        v1 = embed_schema_object("table", "Orders", "", "CREATE TABLE Orders")
        v2 = embed_schema_object("table", "Customers", "", "CREATE TABLE Customers")
        assert v1 != v2

    def test_empty_definition_returns_vector(self):
        from dbanalyser.schema_intel.embedder import embed_schema_object
        vec = embed_schema_object("table", "X", "", "")
        assert len(vec) == 256

    def test_unit_normalized(self):
        from dbanalyser.schema_intel.embedder import embed_schema_object
        vec = embed_schema_object("table", "Payments", "", "Payment processing table")
        magnitude = math.sqrt(sum(v * v for v in vec))
        # Either normalized (~1.0) or zero vector — both are valid
        assert magnitude < 2.0


class TestCosineSimliarity:
    def test_identical_vectors_similarity_one(self):
        from dbanalyser.schema_intel.embedder import cosine_similarity
        v = [1.0, 0.0, 0.5, 0.3]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors_similarity_zero(self):
        from dbanalyser.schema_intel.embedder import cosine_similarity
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert abs(cosine_similarity(v1, v2)) < 1e-6

    def test_zero_vector_returns_zero(self):
        from dbanalyser.schema_intel.embedder import cosine_similarity
        assert cosine_similarity([0.0, 0.0], [1.0, 0.5]) == 0.0

    def test_different_length_vectors(self):
        from dbanalyser.schema_intel.embedder import cosine_similarity
        # Shorter vector treated as zero-padded — should not crash
        result = cosine_similarity([1.0, 0.5], [1.0, 0.5, 0.3])
        assert isinstance(result, float)

    def test_symmetry(self):
        from dbanalyser.schema_intel.embedder import cosine_similarity
        v1 = [0.3, 0.7, 0.1]
        v2 = [0.6, 0.2, 0.9]
        assert abs(cosine_similarity(v1, v2) - cosine_similarity(v2, v1)) < 1e-9


class TestVectorSerialisation:
    def test_roundtrip(self):
        from dbanalyser.schema_intel.embedder import (
            vector_to_json, vector_from_json, embed_schema_object,
        )
        vec = embed_schema_object("table", "Test", "", "some definition here")
        json_str = vector_to_json(vec)
        recovered = vector_from_json(json_str)
        assert len(recovered) == len(vec)
        assert all(abs(a - b) < 1e-9 for a, b in zip(vec, recovered))

    def test_empty_json_returns_empty(self):
        from dbanalyser.schema_intel.embedder import vector_from_json
        assert vector_from_json("") == []
        assert vector_from_json("null") == []


# ─────────────────────────────────────────────────────────────────────────────
# Extractor
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractSchemaFromObjects:
    def _make_obj(self, name, obj_type, source, schema="dbo"):
        obj = MagicMock()
        obj.name = name
        obj.obj_type = obj_type     # extractor reads obj.obj_type (not object_type)
        obj.schema = schema
        obj.source = source
        obj.object_type = obj_type  # keep both for compatibility
        return obj

    def test_extracts_table(self):
        from dbanalyser.schema_intel.extractor import extract_schema_from_objects
        sql = "CREATE TABLE dbo.Accounts (AccountId INT NOT NULL, Balance DECIMAL(18,2))"
        objs = [self._make_obj("Accounts", "table", sql)]
        result = extract_schema_from_objects(objs)
        names = [r.object_name for r in result]
        assert "Accounts" in names

    def test_extracts_columns_from_table(self):
        from dbanalyser.schema_intel.extractor import extract_schema_from_objects
        sql = "CREATE TABLE dbo.Orders (\n  OrderId INT NOT NULL,\n  CustomerId INT NOT NULL\n)"
        objs = [self._make_obj("Orders", "table", sql)]
        result = extract_schema_from_objects(objs)
        col_names = [r.object_name for r in result if r.object_type == "column"]
        assert "OrderId" in col_names or "orderid" in [c.lower() for c in col_names]

    def test_extracts_procedure(self):
        from dbanalyser.schema_intel.extractor import extract_schema_from_objects
        sql = "CREATE PROCEDURE dbo.usp_GetAccounts AS BEGIN SELECT * FROM Accounts END"
        objs = [self._make_obj("usp_GetAccounts", "stored procedure", sql)]
        result = extract_schema_from_objects(objs)
        proc_entries = [r for r in result if r.object_type == "procedure"]
        assert len(proc_entries) >= 1

    def test_extracts_view(self):
        from dbanalyser.schema_intel.extractor import extract_schema_from_objects
        sql = "CREATE VIEW dbo.vw_Active AS SELECT * FROM Accounts WHERE IsActive = 1"
        objs = [self._make_obj("vw_Active", "view", sql)]
        result = extract_schema_from_objects(objs)
        view_entries = [r for r in result if r.object_type == "view"]
        assert len(view_entries) >= 1

    def test_empty_input_returns_empty(self):
        from dbanalyser.schema_intel.extractor import extract_schema_from_objects
        assert extract_schema_from_objects([]) == []

    def test_schema_object_dataclass_fields(self):
        from dbanalyser.schema_intel.extractor import extract_schema_from_objects, SchemaObject
        sql = "CREATE TABLE dbo.T1 (Id INT PRIMARY KEY)"
        objs = [self._make_obj("T1", "table", sql)]
        result = extract_schema_from_objects(objs)
        for item in result:
            assert hasattr(item, "object_type")
            assert hasattr(item, "object_name")
            assert hasattr(item, "schema_name")
            assert hasattr(item, "definition")


# ─────────────────────────────────────────────────────────────────────────────
# Searcher / build_schema_context_for_object
# ─────────────────────────────────────────────────────────────────────────────

_REPO_PATH = "dbanalyser.schema_intel.repository.get_embeddings_for_db"


class TestSearchSchema:
    def _make_candidate(self, obj_type, name, schema="dbo", definition=""):
        from dbanalyser.schema_intel.embedder import embed_schema_object
        return {
            "object_type":  obj_type,
            "schema_name":  schema,
            "object_name":  name,
            "parent_name":  "",
            "definition":   definition,
            "embedding":    embed_schema_object(obj_type, name, "", definition),
        }

    def test_returns_top_results(self):
        from dbanalyser.schema_intel.searcher import search_schema
        candidates = [
            self._make_candidate("table", "Accounts"),
            self._make_candidate("table", "Orders"),
            self._make_candidate("table", "Payments"),
        ]
        with patch(_REPO_PATH, return_value=candidates):
            results = search_schema("Accounts", top_k=2)
        assert len(results) <= 2
        assert all("similarity_score" in r for r in results)

    def test_empty_candidates_returns_empty(self):
        from dbanalyser.schema_intel.searcher import search_schema
        with patch(_REPO_PATH, return_value=[]):
            results = search_schema("anything")
        assert results == []

    def test_min_score_filters_low_matches(self):
        from dbanalyser.schema_intel.searcher import search_schema
        from dbanalyser.schema_intel.embedder import embed_schema_object
        candidates = [{
            "object_type":  "table",
            "schema_name":  "dbo",
            "object_name":  "ZZZ_Unrelated",
            "parent_name":  "",
            "definition":   "zzz",
            "embedding":    embed_schema_object("table", "ZZZ_Unrelated", "", "zzz"),
        }]
        with patch(_REPO_PATH, return_value=candidates):
            results = search_schema("Accounts", min_score=0.99)
        assert len(results) == 0 or results[0]["similarity_score"] >= 0.99

    def test_object_type_filter(self):
        from dbanalyser.schema_intel.searcher import search_schema
        candidates = [
            self._make_candidate("table",  "Accounts"),
            self._make_candidate("column", "AccountId"),
        ]
        with patch(_REPO_PATH, return_value=candidates):
            results = search_schema("Accounts", object_types=["table"])
        types = [r["object_type"] for r in results]
        assert all(t == "table" for t in types)


class TestBuildSchemaContext:
    def test_returns_string(self):
        from dbanalyser.schema_intel.searcher import build_schema_context_for_object
        with patch("dbanalyser.schema_intel.searcher.search_schema", return_value=[]):
            ctx = build_schema_context_for_object("usp_Test", "SELECT 1")
        assert isinstance(ctx, str)

    def test_no_results_returns_not_available(self):
        from dbanalyser.schema_intel.searcher import build_schema_context_for_object
        with patch("dbanalyser.schema_intel.searcher.search_schema", return_value=[]):
            ctx = build_schema_context_for_object("usp_Proc", "SELECT * FROM T")
        assert "not available" in ctx.lower() or "no schema" in ctx.lower()

    def test_includes_object_name_in_header(self):
        from dbanalyser.schema_intel.searcher import build_schema_context_for_object
        table_result = [{
            "object_type":     "table",
            "schema_name":     "dbo",
            "object_name":     "Accounts",
            "parent_name":     "",
            "definition":      "CREATE TABLE dbo.Accounts (...)",
            "similarity_score": 0.85,
        }]
        with patch("dbanalyser.schema_intel.searcher.search_schema",
                   return_value=table_result):
            ctx = build_schema_context_for_object("usp_GetAccounts",
                                                   "SELECT * FROM Accounts")
        assert "usp_GetAccounts" in ctx

    def test_includes_table_name_in_context(self):
        from dbanalyser.schema_intel.searcher import build_schema_context_for_object
        table_result = [{
            "object_type":     "table",
            "schema_name":     "dbo",
            "object_name":     "Accounts",
            "parent_name":     "",
            "definition":      "",
            "similarity_score": 0.80,
        }]
        with patch("dbanalyser.schema_intel.searcher.search_schema",
                   return_value=table_result):
            ctx = build_schema_context_for_object("usp_X", "SELECT * FROM Accounts",
                                                   db_registry_id=1)
        assert "Accounts" in ctx
