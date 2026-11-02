"""Script d'administration Supabase, testé avec une fausse session HTTP (aucun appel réseau)."""
import datetime as dt
import json

from src.supabase_admin import Admin, inactive_users, pull, target_name


class FakeResponse:
    def __init__(self, data=None, content=b"", status=200):
        self.status_code = status
        self._data = data
        self.content = content
        self.text = json.dumps(data) if data is not None else ""

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.headers = {}
        self.calls = []

    def get(self, url, params=None):
        self.calls.append(("GET", url))
        for prefix, response in self.routes.items():
            if url.startswith(prefix):
                return response
        return FakeResponse({}, status=404)


URL = "https://exemple.supabase.co"


def test_target_name_uses_species_or_free_text():
    assert target_name({"proposed_species_id": "Alcedo_atthis"}) == "Alcedo_atthis"
    assert target_name({"proposed_species_id": None, "proposed_species_other": "Alcedo atthis"}) == "autre_Alcedo_atthis"


def test_pull_downloads_photos_by_zone_and_species(tmp_path):
    rows = [{
        "id": "c1", "region": "europe", "predicted_species_id": "Erithacus_rubecula", "predicted_confidence": 0.21,
        "proposed_species_id": None, "proposed_species_other": "Alcedo atthis", "comment": "bec long",
        "model_version": "v1", "photo_path": "u1/abc.jpg",
    }]
    session = FakeSession({
        f"{URL}/rest/v1/corrections": FakeResponse(rows),
        f"{URL}/storage/v1/object/corrections/u1/abc.jpg": FakeResponse(content=b"JPEG"),
    })
    n = pull(Admin(URL, "cle-service", session), tmp_path)
    assert n == 1
    assert (tmp_path / "europe" / "autre_Alcedo_atthis" / "c1.jpg").read_bytes() == b"JPEG"
    assert "bec long" in (tmp_path / "corrections.csv").read_text(encoding="utf-8")
    assert session.headers["Authorization"] == "Bearer cle-service"


def test_inactive_users_considers_recent_observations():
    now = dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc)
    users = {"users": [
        {"id": "ancien", "email": "a@x.fr", "created_at": "2023-01-01T00:00:00Z", "last_sign_in_at": "2023-06-01T00:00:00Z"},
        {"id": "actif", "email": "b@x.fr", "created_at": "2023-01-01T00:00:00Z", "last_sign_in_at": "2023-06-01T00:00:00Z"},
        {"id": "nouveau", "email": "c@x.fr", "created_at": "2026-10-01T00:00:00Z", "last_sign_in_at": None},
    ]}
    session = FakeSession({
        f"{URL}/rest/v1/observations": FakeResponse([{"user_id": "actif", "created_at": "2026-09-01T00:00:00Z"}]),
        f"{URL}/auth/v1/admin/users": FakeResponse(users),
    })
    stale = inactive_users(Admin(URL, "k", session), 2, now)
    assert [u["id"] for u in stale] == ["ancien"]
