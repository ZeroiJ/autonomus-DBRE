#!/usr/bin/env python3
"""Single-entry experiment: PostgreSQL up → GRPO training → reward plot → copy latest checkpoint adapters."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Database / runtime defaults (must run before importing ``train`` → ``dbre``)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
os.chdir(_ROOT)

for key, val in (
    ("DB_USER", "dbre_admin"),
    ("DB_PASSWORD", "dbre_pass"),
    ("DB_HOST", "localhost"),
    ("DB_PORT", "5432"),
    ("DB_NAME", "dbre"),
):
    os.environ.setdefault(key, val)


def _try_pg_connect() -> bool:
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            connect_timeout=5,
        )
        conn.close()
        return True
    except Exception:
        return False


def ensure_postgres() -> None:
    """Wait for PostgreSQL or start a Docker ``postgres:16-alpine`` container."""
    if _try_pg_connect():
        print(f"[DB] Connected to PostgreSQL at {os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}.")
        return

    host = os.environ["DB_HOST"]
    port = os.environ["DB_PORT"]
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    dbname = os.environ["DB_NAME"]
    container = "dbre-postgres-round2"

    print("[DB] PostgreSQL not reachable; starting Docker container...")
    subprocess.run(["docker", "rm", "-f", container], capture_output=True)
    r = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container,
            "-e",
            f"POSTGRES_USER={user}",
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            f"POSTGRES_DB={dbname}",
            "-p",
            f"{port}:5432",
            "postgres:16-alpine",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(
            "Failed to start PostgreSQL via Docker. Start PostgreSQL locally and create role/database, e.g.:\n"
            f"  createuser {user} -P; createdb {dbname} -O {user}\n"
            f"Docker stderr: {r.stderr}",
            file=sys.stderr,
        )
        sys.exit(1)

    for _ in range(90):
        time.sleep(1)
        if _try_pg_connect():
            print(f"[DB] Docker PostgreSQL is ready on {host}:{port}.")
            return

    print("[DB] Timeout waiting for PostgreSQL.", file=sys.stderr)
    sys.exit(1)


def seed_database() -> None:
    """Create tables and seed rows so training hits a warm DB (same as ``DBREEnvironment`` init)."""
    from dbre.database import DBREPostgres

    db = DBREPostgres()
    db.connect()
    db.create_tables()
    db.seed_data()
    try:
        db.conn.close()
    except Exception:
        pass
    print("[DB] Schema created and seeded.")


def copy_latest_checkpoint_adapters(
    grpo_dir: Path = Path("grpo_dbre"),
    dest: Path = Path("dbre_trained"),
) -> None:
    """Copy adapter + tokenizer artifacts from the highest-step checkpoint into ``dest``."""
    checkpoints: list[tuple[int, Path]] = []
    if not grpo_dir.is_dir():
        return
    for p in grpo_dir.glob("checkpoint-*"):
        try:
            step = int(p.name.split("-", 1)[1])
            checkpoints.append((step, p))
        except (IndexError, ValueError):
            continue
    if not checkpoints:
        return
    latest = max(checkpoints, key=lambda x: x[0])[1]
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0

    def _should_copy_adapter_artifact(name: str) -> bool:
        if name == "adapter_config.json":
            return True
        if name.startswith("adapter"):
            return True
        if name.endswith(".safetensors") or name.endswith(".bin"):
            return True
        return False

    for path in latest.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if _should_copy_adapter_artifact(name):
            shutil.copy2(path, dest / name)
            copied += 1
    if copied:
        print(f"[Artifacts] Copied {copied} adapter weight file(s) from {latest} → {dest}")
    else:
        print(f"[Artifacts] No adapter weight files in {latest}; relying on train.py save to {dest}")


def plot_reward_curve(rewards: list[float], out_path: Path) -> None:
    import matplotlib.pyplot as plt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rewards:
        plt.figure(figsize=(10, 5))
        plt.text(0.5, 0.5, "No reward batches recorded", ha="center", va="center")
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f"[Plot] Saved empty placeholder to {out_path}")
        return
    xs = list(range(1, len(rewards) + 1))
    plt.figure(figsize=(10, 5))
    plt.plot(xs, rewards, marker="o", markersize=2, linewidth=1)
    plt.xlabel("Reward batch index")
    plt.ylabel("Mean reward (0–1)")
    plt.title("Training reward curve")
    plt.ylim(0.0, 1.0)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"[Plot] Saved {out_path}")


def main() -> None:
    ensure_postgres()
    seed_database()

    # Import after env + DB are ready
    from train import run_training

    results_dir = _ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    rewards = run_training(
        output_dir=str(_ROOT / "grpo_dbre"),
        save_dir=str(_ROOT / "dbre_trained"),
        max_steps=300,
        save_steps=50,
    )

    plot_reward_curve(rewards, results_dir / "reward_curve.png")
    copy_latest_checkpoint_adapters(_ROOT / "grpo_dbre", _ROOT / "dbre_trained")

    print("")
    print("=" * 60)
    print("Training completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
