"""Unit tests for the data_transformation endpoint and transformer module."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.interface.routes.data_transformation import router
from src.modules.data_transformer import (
    TransformationError,
    apply_pipeline,
    available_operations,
)


# ---------------------------------------------------------------------------
# Transformer unit tests
# ---------------------------------------------------------------------------

class TestAvailableOperations:
    def test_returns_list_of_strings(self):
        ops = available_operations()
        assert isinstance(ops, list)
        assert all(isinstance(o, str) for o in ops)

    def test_includes_core_operations(self):
        ops = available_operations()
        for name in ("rename_keys", "filter_keys", "cast_types", "add_metadata", "flatten"):
            assert name in ops


class TestRenameKeys:
    def test_renames_specified_keys(self):
        result = apply_pipeline(
            {"old_name": 1, "keep": 2},
            [{"operation": "rename_keys", "params": {"mapping": {"old_name": "new_name"}}}],
        )
        assert "new_name" in result
        assert "old_name" not in result
        assert result["keep"] == 2

    def test_passthrough_unmapped_keys(self):
        result = apply_pipeline(
            {"a": 1},
            [{"operation": "rename_keys", "params": {"mapping": {}}}],
        )
        assert result == {"a": 1}

    def test_invalid_mapping_raises(self):
        with pytest.raises(TransformationError):
            apply_pipeline(
                {"a": 1},
                [{"operation": "rename_keys", "params": {"mapping": "not-a-dict"}}],
            )


class TestFilterKeys:
    def test_keeps_only_specified_keys(self):
        result = apply_pipeline(
            {"a": 1, "b": 2, "c": 3},
            [{"operation": "filter_keys", "params": {"keys": ["a", "c"]}}],
        )
        assert result == {"a": 1, "c": 3}

    def test_missing_keys_ignored(self):
        result = apply_pipeline(
            {"x": 10},
            [{"operation": "filter_keys", "params": {"keys": ["x", "y"]}}],
        )
        assert result == {"x": 10}


class TestCastTypes:
    def test_cast_string_to_int(self):
        result = apply_pipeline(
            {"count": "42"},
            [{"operation": "cast_types", "params": {"casts": {"count": "int"}}}],
        )
        assert result["count"] == 42
        assert isinstance(result["count"], int)

    def test_cast_float_to_str(self):
        result = apply_pipeline(
            {"price": 3.14},
            [{"operation": "cast_types", "params": {"casts": {"price": "str"}}}],
        )
        assert result["price"] == "3.14"

    def test_invalid_cast_raises(self):
        with pytest.raises(TransformationError):
            apply_pipeline(
                {"val": "not-a-number"},
                [{"operation": "cast_types", "params": {"casts": {"val": "int"}}}],
            )

    def test_unsupported_type_raises(self):
        with pytest.raises(TransformationError):
            apply_pipeline(
                {"val": "x"},
                [{"operation": "cast_types", "params": {"casts": {"val": "datetime"}}}],
            )


class TestAddMetadata:
    def test_adds_timestamp(self):
        result = apply_pipeline(
            {"a": 1},
            [{"operation": "add_metadata", "params": {"add_timestamp": True}}],
        )
        assert "_transformed_at" in result

    def test_adds_checksum(self):
        result = apply_pipeline(
            {"a": 1},
            [{"operation": "add_metadata", "params": {"add_checksum": True}}],
        )
        assert "_checksum" in result
        assert len(result["_checksum"]) == 64  # sha256 hex


class TestFlatten:
    def test_flattens_nested_dict(self):
        result = apply_pipeline(
            {"user": {"name": "Alice", "age": 30}, "score": 99},
            [{"operation": "flatten", "params": {"separator": "."}}],
        )
        assert result["user.name"] == "Alice"
        assert result["user.age"] == 30
        assert result["score"] == 99

    def test_default_separator_is_underscore(self):
        result = apply_pipeline(
            {"a": {"b": 1}},
            [{"operation": "flatten", "params": {}}],
        )
        assert "a_b" in result


class TestRegexReplace:
    def test_replaces_pattern(self):
        result = apply_pipeline(
            {"email": "user@example.com"},
            [{"operation": "regex_replace", "params": {
                "field": "email", "pattern": r"@.*", "replacement": "@redacted"
            }}],
        )
        assert result["email"] == "user@redacted"

    def test_missing_field_no_error(self):
        result = apply_pipeline(
            {"name": "Alice"},
            [{"operation": "regex_replace", "params": {
                "field": "nonexistent", "pattern": "x", "replacement": ""
            }}],
        )
        assert result == {"name": "Alice"}

    def test_invalid_regex_raises(self):
        with pytest.raises(TransformationError):
            apply_pipeline(
                {"val": "test"},
                [{"operation": "regex_replace", "params": {
                    "field": "val", "pattern": "[", "replacement": ""
                }}],
            )


class TestPipeline:
    def test_multi_step_pipeline(self):
        result = apply_pipeline(
            {"first_name": "Bob", "age": "25", "ignored": True},
            [
                {"operation": "filter_keys", "params": {"keys": ["first_name", "age"]}},
                {"operation": "rename_keys", "params": {"mapping": {"first_name": "name"}}},
                {"operation": "cast_types", "params": {"casts": {"age": "int"}}},
            ],
        )
        assert result == {"name": "Bob", "age": 25}
        assert "ignored" not in result

    def test_unknown_operation_raises(self):
        with pytest.raises(TransformationError, match="unknown operation"):
            apply_pipeline({"a": 1}, [{"operation": "does_not_exist", "params": {}}])

    def test_missing_operation_key_raises(self):
        with pytest.raises(TransformationError, match="'operation' is required"):
            apply_pipeline({"a": 1}, [{"params": {}}])


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


class TestEndpointHappyPath:
    def test_simple_rename(self, client: TestClient):
        resp = client.post("/data_transformation", json={
            "data": {"old": "value"},
            "pipeline": [{"operation": "rename_keys", "params": {"mapping": {"old": "new"}}}],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["result"] == {"new": "value"}
        assert body["steps_applied"] == 1
        assert "request_id" in body
        assert body["duration_ms"] >= 0

    def test_caller_request_id_preserved(self, client: TestClient):
        resp = client.post("/data_transformation", json={
            "data": {"x": 1},
            "pipeline": [{"operation": "filter_keys", "params": {"keys": ["x"]}}],
            "request_id": "caller-abc-123",
        })
        assert resp.json()["request_id"] == "caller-abc-123"

    def test_multi_step_pipeline(self, client: TestClient):
        resp = client.post("/data_transformation", json={
            "data": {"a": "1", "b": "drop"},
            "pipeline": [
                {"operation": "filter_keys", "params": {"keys": ["a"]}},
                {"operation": "cast_types", "params": {"casts": {"a": "int"}}},
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["result"] == {"a": 1}


class TestEndpointValidation:
    def test_empty_pipeline_rejected(self, client: TestClient):
        resp = client.post("/data_transformation", json={
            "data": {"x": 1},
            "pipeline": [],
        })
        assert resp.status_code == 422

    def test_unknown_operation_rejected_at_validation(self, client: TestClient):
        resp = client.post("/data_transformation", json={
            "data": {"x": 1},
            "pipeline": [{"operation": "not_real", "params": {}}],
        })
        assert resp.status_code == 422

    def test_missing_data_field_rejected(self, client: TestClient):
        resp = client.post("/data_transformation", json={
            "pipeline": [{"operation": "filter_keys", "params": {"keys": []}}],
        })
        assert resp.status_code == 422

    def test_missing_pipeline_field_rejected(self, client: TestClient):
        resp = client.post("/data_transformation", json={"data": {"x": 1}})
        assert resp.status_code == 422


class TestEndpointTransformationErrors:
    def test_invalid_cast_returns_400(self, client: TestClient):
        resp = client.post("/data_transformation", json={
            "data": {"val": "not-a-number"},
            "pipeline": [{"operation": "cast_types", "params": {"casts": {"val": "int"}}}],
        })
        assert resp.status_code == 400
        body = resp.json()
        assert body["status"] == "error"
        assert "TransformationError" in body["error"]
        assert "request_id" in body

    def test_invalid_regex_returns_400(self, client: TestClient):
        resp = client.post("/data_transformation", json={
            "data": {"text": "hello"},
            "pipeline": [{"operation": "regex_replace", "params": {
                "field": "text", "pattern": "[", "replacement": ""
            }}],
        })
        assert resp.status_code == 400
