"""Run the real pipeline on sample contracts and compare statuses with expected.json.
Usage (stack running):  docker compose exec backend python -m eval.run_eval"""
import json
import pathlib

from app import db
from app.pipeline import run_pipeline

SAMPLES = pathlib.Path(__file__).parent / "samples"
USER = "eval-user"


def main() -> None:
    db.init_db()
    expected = json.loads((SAMPLES / "expected.json").read_text())
    right = total = quotes = 0
    for name, want in expected.items():
        raw = (SAMPLES / name).read_bytes()
        row = db.fetch("INSERT INTO contracts (user_id, filename, size_bytes) VALUES (%s,%s,%s) RETURNING id",
                       (USER, name, len(raw)), one=True)
        run_pipeline(row["id"], USER, name, raw)
        got = {r["item_key"]: r for r in db.fetch(
            "SELECT item_key, status, quote FROM reviews WHERE contract_id=%s AND user_id=%s", (row["id"], USER))}
        print(f"\n{name}")
        for key, status in want.items():
            g = got.get(key, {}).get("status", "missing")
            ok = g == status
            right, total = right + ok, total + 1
            quotes += bool(got.get(key, {}).get("quote"))
            print(f"  {'OK ' if ok else 'BAD'} {key:16} expected={status:10} got={g}")
        db.fetch("DELETE FROM contracts WHERE id=%s AND user_id=%s", (row["id"], USER))
    print(f"\nScore: {right}/{total} items correct ({100 * right // total}%). Verified quotes returned: {quotes}.")


if __name__ == "__main__":
    main()
