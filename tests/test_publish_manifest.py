"""Logique de versionnement du manifeste des modèles (sans réseau)."""
import pytest

from src.publish_model import merge_manifest, model_readme, rollback_manifest


def card(version, acc):
    return {
        "region": "europe",
        "label": "France métropolitaine",
        "version": version,
        "architecture": "convnext_tiny",
        "file": "model_int8.onnx",
        "size_mb": 28.4,
        "img_size": 224,
        "resize": 256,
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
        "metrics": {"test_acc": acc},
        "evaluation": {"pytorch": {}},
        "classes": [{"id": "Turdus_merula", "fr": "Merle noir", "sci": "Turdus merula"}],
    }


def test_first_publication_creates_region_and_history():
    m = merge_manifest({}, card("v1", 0.80), "europe/v1/model.onnx", "2026-11-02T20:00:00+00:00")
    assert m["regions"]["europe"]["file"] == "europe/v1/model.onnx"
    assert m["regions"]["europe"]["classes"][0]["id"] == "Turdus_merula"
    assert "evaluation" not in m["regions"]["europe"]
    assert [h["version"] for h in m["history"]["europe"]] == ["v1"]
    assert "classes" not in m["history"]["europe"][0]


def test_new_version_keeps_history_and_other_regions():
    m = {"regions": {"antilles": {"version": "a1"}}, "history": {"antilles": [{"version": "a1"}]}}
    m = merge_manifest(m, card("v1", 0.80), "europe/v1/model.onnx", "t1")
    m = merge_manifest(m, card("v2", 0.83), "europe/v2/model.onnx", "t2")
    assert m["regions"]["antilles"]["version"] == "a1"
    assert m["regions"]["europe"]["version"] == "v2"
    assert [h["version"] for h in m["history"]["europe"]] == ["v1", "v2"]


def test_republishing_same_version_does_not_duplicate_history():
    m = merge_manifest({}, card("v1", 0.80), "europe/v1/model.onnx", "t1")
    m = merge_manifest(m, card("v1", 0.81), "europe/v1/model.onnx", "t2")
    assert len(m["history"]["europe"]) == 1


def test_rollback_restores_previous_file_and_metrics():
    m = merge_manifest({}, card("v1", 0.80), "europe/v1/model.onnx", "t1")
    m = merge_manifest(m, card("v2", 0.75), "europe/v2/model.onnx", "t2")
    m = rollback_manifest(m, "europe", "v1", m["regions"]["europe"]["classes"], "t3")
    assert m["regions"]["europe"]["version"] == "v1"
    assert m["regions"]["europe"]["file"] == "europe/v1/model.onnx"
    assert m["regions"]["europe"]["metrics"]["test_acc"] == 0.80
    assert m["regions"]["europe"]["classes"]


def test_rollback_to_unknown_version_fails():
    m = merge_manifest({}, card("v1", 0.80), "europe/v1/model.onnx", "t1")
    with pytest.raises(SystemExit):
        rollback_manifest(m, "europe", "v9", [], "t2")


def test_readme_declares_non_commercial_license():
    m = merge_manifest({}, card("v1", 0.80), "europe/v1/model.onnx", "t1")
    text = model_readme(m)
    assert "license: cc-by-nc-4.0" in text
    assert "France métropolitaine" in text
