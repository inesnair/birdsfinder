"""
Administration de BirdsFinder depuis Colab : corrections des professionnels, comptes pro, purge RGPD.

Utilise la clé "service_role" de Supabase, qui contourne les règles de sécurité :
elle ne doit JAMAIS être dans le front ni sur GitHub. Dans Colab, mets-la dans les secrets (icône clé) :
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Commandes :
    python -m src.supabase_admin pending                         # corrections et demandes pro en attente
    python -m src.supabase_admin pull --out data/corrections     # télécharge les photos à vérifier
    python -m src.supabase_admin review <id> --accept            # ou --reject
    python -m src.supabase_admin approve-pro <e-mail>            # active les corrections pour ce compte
    python -m src.supabase_admin export-accepted --out data/corrections_ok   # photos validées, rangées par espèce
    python -m src.supabase_admin purge-inactive --years 2        # liste les comptes inactifs ; --apply pour supprimer

Les photos acceptées rejoignent ensuite le dossier d'entraînement de leur zone (ex. data/raw_europe/<espèce>/)
avant de relancer train_cnn, export_onnx puis publish_model.
"""
import argparse
import csv
import datetime as dt
import os
from pathlib import Path

BUCKET = "corrections"


def secret(name: str) -> str:
    value = os.getenv(name)
    if not value:
        try:
            from google.colab import userdata  # type: ignore

            value = userdata.get(name)
        except Exception:
            value = None
    if not value:
        raise SystemExit(f"{name} introuvable (secrets Colab ou variable d'environnement).")
    return value


class Admin:
    def __init__(self, url: str, key: str, session=None):
        if session is None:
            import requests

            session = requests.Session()
        self.url = url.rstrip("/")
        self.s = session
        self.s.headers.update({"apikey": key, "Authorization": f"Bearer {key}"})

    def _ok(self, r):
        if r.status_code >= 300:
            raise SystemExit(f"Erreur Supabase {r.status_code} : {r.text[:300]}")
        return r

    # --- tables (API REST PostgREST) ---
    def select(self, table: str, query: str) -> list:
        return self._ok(self.s.get(f"{self.url}/rest/v1/{table}?{query}")).json()

    def update(self, table: str, match: str, values: dict):
        self._ok(self.s.patch(f"{self.url}/rest/v1/{table}?{match}", json=values, headers={"Prefer": "return=minimal"}))

    # --- stockage ---
    def download(self, path: str) -> bytes:
        return self._ok(self.s.get(f"{self.url}/storage/v1/object/{BUCKET}/{path}")).content

    def remove_user_photos(self, user_id: str):
        listing = self._ok(self.s.post(f"{self.url}/storage/v1/object/list/{BUCKET}",
                                       json={"prefix": user_id, "limit": 1000})).json()
        paths = [f"{user_id}/{f['name']}" for f in listing]
        if paths:
            self._ok(self.s.delete(f"{self.url}/storage/v1/object/{BUCKET}", json={"prefixes": paths}))
        return len(paths)

    # --- comptes (API d'administration Auth) ---
    def users(self) -> list:
        out, page = [], 1
        while True:
            batch = self._ok(self.s.get(f"{self.url}/auth/v1/admin/users", params={"page": page, "per_page": 1000})).json()
            users = batch.get("users", batch if isinstance(batch, list) else [])
            out += users
            if len(users) < 1000:
                return out
            page += 1

    def delete_user(self, user_id: str):
        self._ok(self.s.delete(f"{self.url}/auth/v1/admin/users/{user_id}"))


def target_name(c: dict) -> str:
    """Dossier de l'espèce proposée (ou « autre_<nom> » pour une espèce hors liste)."""
    if c.get("proposed_species_id"):
        return c["proposed_species_id"]
    other = "".join(ch if ch.isalnum() else "_" for ch in (c.get("proposed_species_other") or "inconnue")).strip("_")
    return f"autre_{other}"


def pull(admin: Admin, out: Path, status: str = "pending") -> int:
    rows = admin.select("corrections", f"status=eq.{status}&order=created_at.asc&select=*")
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "corrections.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "zone", "predit", "confiance", "propose", "commentaire", "version_modele", "fichier"])
        for c in rows:
            dest = out / c["region"] / target_name(c) / f"{c['id']}.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(admin.download(c["photo_path"]))
            w.writerow([c["id"], c["region"], c["predicted_species_id"], c.get("predicted_confidence"),
                        target_name(c), c.get("comment") or "", c.get("model_version") or "", str(dest)])
    return len(rows)


def inactive_users(admin: Admin, years: float, now: dt.datetime) -> list:
    limit = now - dt.timedelta(days=365.25 * years)
    recent_obs = {o["user_id"]: o["created_at"] for o in admin.select("observations", "select=user_id,created_at&order=created_at.asc")}
    stale = []
    for u in admin.users():
        dates = [u.get("last_sign_in_at"), u.get("created_at"), recent_obs.get(u["id"])]
        last = max(dt.datetime.fromisoformat(d.replace("Z", "+00:00")) for d in dates if d)
        if last < limit:
            stale.append({"id": u["id"], "email": u.get("email"), "last_activity": last.isoformat()})
    return stale


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pending")
    p = sub.add_parser("pull")
    p.add_argument("--out", default="data/corrections")
    r = sub.add_parser("review")
    r.add_argument("id")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--accept", action="store_true")
    g.add_argument("--reject", action="store_true")
    a = sub.add_parser("approve-pro")
    a.add_argument("email")
    e = sub.add_parser("export-accepted")
    e.add_argument("--out", default="data/corrections_ok")
    k = sub.add_parser("purge-inactive")
    k.add_argument("--years", type=float, default=2)
    k.add_argument("--apply", action="store_true", help="sans cette option : simple liste, rien n'est supprimé")
    args = ap.parse_args()

    admin = Admin(secret("SUPABASE_URL"), secret("SUPABASE_SERVICE_ROLE_KEY"))
    now = dt.datetime.now(dt.timezone.utc)

    if args.cmd == "pending":
        for c in admin.select("corrections", "status=eq.pending&order=created_at.asc&select=*"):
            print(f"{c['id']}  {c['region']}  {c['predicted_species_id']} -> {target_name(c)}  {c.get('comment') or ''}")
        for pr in admin.select("profiles", "pro_requested=eq.true&role=eq.amateur&select=id,display_name,organisation"):
            print(f"Demande pro : {pr.get('display_name')} ({pr.get('organisation')})  id={pr['id']}")
    elif args.cmd == "pull":
        n = pull(admin, Path(args.out))
        print(f"{n} correction(s) téléchargée(s) dans {args.out} (voir corrections.csv)")
    elif args.cmd == "review":
        status = "accepted" if args.accept else "rejected"
        admin.update("corrections", f"id=eq.{args.id}", {"status": status, "reviewed_at": now.isoformat()})
        print(f"Correction {args.id} : {status}")
    elif args.cmd == "approve-pro":
        user = next((u for u in admin.users() if (u.get("email") or "").lower() == args.email.lower()), None)
        if not user:
            raise SystemExit(f"Aucun compte pour {args.email}")
        admin.update("profiles", f"id=eq.{user['id']}", {"role": "pro"})
        print(f"{args.email} est maintenant professionnel : le bouton « Proposer une correction » apparaît.")
    elif args.cmd == "export-accepted":
        n = pull(admin, Path(args.out), status="accepted")
        print(f"{n} photo(s) validée(s) dans {args.out}/<zone>/<espèce>/ : copie-les dans data/raw_<zone>/ avant l'entraînement")
    elif args.cmd == "purge-inactive":
        stale = inactive_users(admin, args.years, now)
        for u in stale:
            print(f"Inactif depuis {u['last_activity'][:10]} : {u['email']}")
        if args.apply:
            for u in stale:
                admin.remove_user_photos(u["id"])
                admin.delete_user(u["id"])  # profil, observations, corrections suivent en cascade
            print(f"{len(stale)} compte(s) supprimé(s).")
        else:
            print(f"{len(stale)} compte(s) concerné(s). Relance avec --apply pour les supprimer.")


if __name__ == "__main__":
    main()
