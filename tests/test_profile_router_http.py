from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.routers import profile as profile_router


def _write_example_profile(base_dir: Path) -> None:
    example_dir = base_dir / "example"
    example_dir.mkdir(parents=True, exist_ok=True)
    (example_dir / "search_config.yaml").write_text("keywords: {}\n", encoding="utf-8")
    (example_dir / "profile_doc.md").write_text("# Candidate Profile\n", encoding="utf-8")
    (example_dir / "scoring_philosophy.md").write_text("Score by evidence.\n", encoding="utf-8")
    (example_dir / "companies.yaml").write_text("greenhouse: []\n", encoding="utf-8")


def test_profile_endpoints_create_list_and_update_files(monkeypatch, tmp_path):
    _write_example_profile(tmp_path)
    monkeypatch.setattr(profile_router, "PROFILES_DIR", tmp_path)

    with TestClient(app) as client:
        create_response = client.post("/api/profile/demo")

        assert create_response.status_code == 200
        assert create_response.json() == {"ok": True, "name": "demo"}
        assert (tmp_path / "demo" / "search_config.yaml").exists()

        list_response = client.get("/api/profiles")

        assert list_response.status_code == 200
        names = [item["name"] for item in list_response.json()]
        assert names == ["demo", "example"]

        get_yaml_response = client.get("/api/profile/demo/yaml")

        assert get_yaml_response.status_code == 200
        assert get_yaml_response.json()["content"] == "keywords: {}\n"

        put_yaml_response = client.put(
            "/api/profile/demo/yaml",
            json={"content": "keywords:\n  title_patterns:\n    high_confidence: []\n"},
        )

        assert put_yaml_response.status_code == 200
        assert (tmp_path / "demo" / "search_config.yaml").read_text(encoding="utf-8").startswith("keywords:")

        invalid_yaml_response = client.put(
            "/api/profile/demo/yaml",
            json={"content": "keywords: [\n"},
        )

        assert invalid_yaml_response.status_code == 422
        assert "Invalid YAML" in invalid_yaml_response.json()["detail"]

        put_doc_response = client.put(
            "/api/profile/demo/doc",
            json={"content": "# Updated Profile\n"},
        )

        assert put_doc_response.status_code == 200
        assert (tmp_path / "demo" / "profile_doc.md").read_text(encoding="utf-8") == "# Updated Profile\n"

        scoring_response = client.put(
            "/api/profile/demo/scoring-philosophy",
            json={"content": "Bias toward strong evidence.\n"},
        )

        assert scoring_response.status_code == 200
        assert (tmp_path / "demo" / "scoring_philosophy.md").read_text(encoding="utf-8") == "Bias toward strong evidence.\n"


def test_profile_endpoints_return_expected_errors(monkeypatch, tmp_path):
    _write_example_profile(tmp_path)
    monkeypatch.setattr(profile_router, "PROFILES_DIR", tmp_path)

    with TestClient(app) as client:
        duplicate_response = client.post("/api/profile/example")
        missing_doc_response = client.get("/api/profile/missing/doc")
        empty_scoring_response = client.put(
            "/api/profile/example/scoring-philosophy",
            json={"content": "   "},
        )

        assert duplicate_response.status_code == 409
        assert "already exists" in duplicate_response.json()["detail"]
        assert missing_doc_response.status_code == 404
        assert empty_scoring_response.status_code == 422
