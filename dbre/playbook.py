from __future__ import annotations

import base64
import io
import json
import os
from datetime import datetime
from typing import Any

import difflib
import matplotlib.pyplot as plt


class ELOSystem:
    """ELO rating system for comparing playbook versions."""

    def __init__(self, k_factor: int = 32, initial_elo: float = 1000.0) -> None:
        """Initialize ELO system with k-factor and starting rating."""
        self.k_factor = k_factor
        self.initial_elo = initial_elo

    def calculate_expected_score(self, elo_a: float, elo_b: float) -> float:
        """Calculate expected score for player A against player B."""
        return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

    def update_elo(self, winner_elo: float, loser_elo: float) -> tuple[float, float]:
        """Update ELO ratings after a match and return new ratings."""
        expected_winner = self.calculate_expected_score(winner_elo, loser_elo)
        expected_loser = self.calculate_expected_score(loser_elo, winner_elo)

        new_winner_elo = winner_elo + self.k_factor * (1 - expected_winner)
        new_loser_elo = loser_elo + self.k_factor * (0 - expected_loser)

        return round(new_winner_elo, 2), round(new_loser_elo, 2)


def plot_elo_curve(history: list[dict]) -> str:
    """Generate ELO rating curve plot and return as base64 PNG string."""
    plt.style.use('dark_background')

    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a2e')
    ax.set_facecolor('#1a1a2e')

    versions = [h["version"] for h in history]
    elos = [h["elo"] for h in history]

    ax.plot(versions, elos, color='#00ff88', linewidth=2, marker='o', markersize=8)

    ax.set_xlabel('Version', color='white', fontsize=12)
    ax.set_ylabel('ELO Rating', color='white', fontsize=12)
    ax.set_title('Playbook ELO Rating Over Time', color='white', fontsize=14, fontweight='bold')

    ax.tick_params(axis='x', colors='white', rotation=45)
    ax.tick_params(axis='y', colors='white')

    ax.grid(True, color='#333333', linestyle='--', alpha=0.5)

    for i, (version, elo) in enumerate(zip(versions, elos)):
        ax.annotate(f'{elo:.0f}', (i, elo), textcoords="offset points", xytext=(0, 10), ha='center', color='white', fontsize=9)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#1a1a2e', dpi=100)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    return img_base64


DEFAULT_PLAYBOOK = """# DBRE Diagnostic Playbook v1
## Priority Order:
1. Check EXPLAIN ANALYZE for sequential scans → always add index if found
2. Check for N+1 patterns → rewrite as JOIN
3. Check join order → put smallest table first
4. Check for SELECT * → replace with specific columns
5. Check for functions on indexed columns → rewrite to use index
6. Verify correctness by comparing row count with original
"""


class PlaybookManager:
    def __init__(self, storage_path: str = "./playbook_versions/") -> None:
        self.storage_path = storage_path
        self.current_playbook: str = DEFAULT_PLAYBOOK
        self._ensure_storage_exists()
        self._load_current_if_exists()

    def _ensure_storage_exists(self) -> None:
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)

    def _load_current_if_exists(self) -> None:
        current_file = os.path.join(self.storage_path, "current.md")
        if os.path.exists(current_file):
            with open(current_file, "r", encoding="utf-8") as f:
                self.current_playbook = f.read()

    def _save_current(self) -> None:
        current_file = os.path.join(self.storage_path, "current.md")
        with open(current_file, "w", encoding="utf-8") as f:
            f.write(self.current_playbook)

    def _get_next_version_number(self) -> int:
        history = self.get_version_history()
        if not history:
            return 1
        return max(v["version_number"] for v in history) + 1

    def get_current(self) -> str:
        return self.current_playbook

    def apply_diff(self, diff_text: str) -> str:
        old_playbook = self.current_playbook
        old_lines = old_playbook.splitlines(keepends=True)

        if not old_lines or not old_lines[-1].endswith('\n'):
            if old_lines:
                old_lines[-1] += '\n'
            else:
                old_lines = ['\n']

        patched_lines = list(old_lines)

        diff_lines = diff_text.splitlines()
        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]

            if line.startswith('@@'):
                parts = line.split()
                old_range = parts[1][1:]

                if ',' in old_range:
                    start_line, count = map(int, old_range.split(','))
                else:
                    start_line = int(old_range)
                    count = 1

                start_idx = start_line - 1

                old_content = []
                new_content = []
                i += 1

                while i < len(diff_lines) and not diff_lines[i].startswith('@@'):
                    dl = diff_lines[i]
                    if dl.startswith('-'):
                        old_content.append(dl[1:] + '\n')
                    elif dl.startswith('+'):
                        new_content.append(dl[1:] + '\n')
                    elif dl.startswith(' '):
                        old_content.append(dl[1:] + '\n')
                        new_content.append(dl[1:] + '\n')
                    elif dl == '\\ No newline at end of file':
                        pass
                    i += 1

                if start_idx < len(patched_lines) and count > 0:
                    end_idx = min(start_idx + count, len(patched_lines))
                    patched_lines = patched_lines[:start_idx] + new_content + patched_lines[end_idx:]

                continue

            i += 1

        new_playbook = ''.join(patched_lines)
        self.current_playbook = new_playbook
        self._save_current()

        return new_playbook

    def archive_version(self, version_number: int, content: str, elo_score: float) -> None:
        version_file = os.path.join(self.storage_path, f"v{version_number}.md")
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(content)

        metadata_file = os.path.join(self.storage_path, "versions.json")
        metadata = []
        if os.path.exists(metadata_file):
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        metadata.append({
            "version_number": version_number,
            "timestamp": datetime.now().isoformat(),
            "elo_score": elo_score,
            "filename": f"v{version_number}.md"
        })

        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def get_version_history(self) -> list[dict[str, Any]]:
        metadata_file = os.path.join(self.storage_path, "versions.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def revert_to_version(self, version_number: int) -> None:
        version_file = os.path.join(self.storage_path, f"v{version_number}.md")
        if os.path.exists(version_file):
            with open(version_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.current_playbook = content
            self._save_current()
