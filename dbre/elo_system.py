import json
import os
import time
from typing import List, Dict, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64


class ELOSystem:
    """Core ELO rating calculation system."""

    def __init__(self, k_factor: int = 32, initial_elo: float = 1000.0):
        self.k_factor = k_factor
        self.initial_elo = initial_elo

    def calculate_expected_score(self, elo_a: float, elo_b: float) -> float:
        """Calculate expected win probability for player A vs player B."""
        return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))

    def update_elo(self, winner_elo: float, loser_elo: float) -> Tuple[float, float]:
        """Update ELO ratings after a match. Returns (new_winner_elo, new_loser_elo)."""
        expected_winner = self.calculate_expected_score(winner_elo, loser_elo)
        expected_loser = 1.0 - expected_winner

        new_winner = winner_elo + self.k_factor * (1.0 - expected_winner)
        new_loser = loser_elo + self.k_factor * (0.0 - expected_loser)

        return round(new_winner, 2), round(new_loser, 2)


class PlaybookELOTracker:
    """Tracks ELO ratings for playbook versions with persistence."""

    def __init__(self, storage_path: str = "./elo_history/"):
        self.storage_path = storage_path
        self.elo_system = ELOSystem()
        self.history: List[Dict] = []
        os.makedirs(storage_path, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load ELO history from disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                self.history = json.load(f)

    def _save(self) -> None:
        """Save ELO history to disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        with open(history_file, "w") as f:
            json.dump(self.history, f, indent=2, default=str)

    def register_playbook(self, version: str, elo: float = 1000.0) -> None:
        """Register a new playbook version with initial ELO."""
        entry = {
            "version": version,
            "elo": elo,
            "timestamp": time.time(),
            "matches_played": 0,
            "matches_won": 0
        }
        self.history.append(entry)
        self._save()

    def get_current_elo(self, version: str) -> float:
        """Get the current ELO for a playbook version."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                return entry["elo"]
        return self.elo_system.initial_elo

    def record_matchup(self, version_a: str, version_b: str, winner: str) -> Tuple[float, float]:
        """Record a match between two playbook versions. Returns (new_elo_a, new_elo_b)."""
        elo_a = self.get_current_elo(version_a)
        elo_b = self.get_current_elo(version_b)

        if winner == version_a:
            new_a, new_b = self.elo_system.update_elo(elo_a, elo_b)
        elif winner == version_b:
            new_b, new_a = self.elo_system.update_elo(elo_b, elo_a)
        else:
            raise ValueError(f"Winner must be one of the two versions: {version_a} or {version_b}")

        self._update_entry(version_a, new_a, version_a == winner)
        self._update_entry(version_b, new_b, version_b == winner)

        return new_a, new_b

    def _update_entry(self, version: str, new_elo: float, won: bool) -> None:
        """Update a single entry in history."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                entry["elo"] = new_elo
                entry["matches_played"] += 1
                if won:
                    entry["matches_won"] += 1
                entry["timestamp"] = time.time()
                break
        else:
            self.register_playbook(version, new_elo)
            for entry in reversed(self.history):
                if entry["version"] == version:
                    entry["matches_played"] = 1
                    if won:
                        entry["matches_won"] = 1
                    break
        self._save()

    def get_elo_history(self) -> List[Dict]:
        """Return full ELO history for plotting."""
        return self.history

    def get_current_champion(self) -> str:
        """Return the version with the highest ELO."""
        if not self.history:
            return "none"
        return max(self.history, key=lambda x: x["elo"])["version"]

    def get_elo_curve_data(self) -> Dict:
        """Return data formatted for plotting: {versions: [], elos: [], timestamps: []}."""
        sorted_history = sorted(self.history, key=lambda x: x["timestamp"])
        return {
            "versions": [h["version"] for h in sorted_history],
            "elos": [h["elo"] for h in sorted_history],
            "timestamps": [h["timestamp"] for h in sorted_history],
            "matches_played": [h["matches_played"] for h in sorted_history],
            "matches_won": [h["matches_won"] for h in sorted_history]
        }


class ELOSystem:
    """Core ELO rating calculation system."""

    def __init__(self, k_factor: int = 32, initial_elo: float = 1000.0):
        self.k_factor = k_factor
        self.initial_elo = initial_elo

    def calculate_expected_score(self, elo_a: float, elo_b: float) -> float:
        """Calculate expected win probability for player A vs player B."""
        return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))

    def update_elo(self, winner_elo: float, loser_elo: float) -> Tuple[float, float]:
        """Update ELO ratings after a match. Returns (new_winner_elo, new_loser_elo)."""
        expected_winner = self.calculate_expected_score(winner_elo, loser_elo)
        expected_loser = 1.0 - expected_winner

        new_winner = winner_elo + self.k_factor * (1.0 - expected_winner)
        new_loser = loser_elo + self.k_factor * (0.0 - expected_loser)

        return round(new_winner, 2), round(new_loser, 2)


class PlaybookELOTracker:
    """Tracks ELO ratings for playbook versions with persistence."""

    def __init__(self, storage_path: str = "./elo_history/"):
        self.storage_path = storage_path
        self.elo_system = ELOSystem()
        self.history: List[Dict] = []
        os.makedirs(storage_path, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load ELO history from disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                self.history = json.load(f)

    def _save(self) -> None:
        """Save ELO history to disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        with open(history_file, "w") as f:
            json.dump(self.history, f, indent=2, default=str)

    def register_playbook(self, version: str, elo: float = 1000.0) -> None:
        """Register a new playbook version with initial ELO."""
        entry = {
            "version": version,
            "elo": elo,
            "timestamp": time.time(),
            "matches_played": 0,
            "matches_won": 0
        }
        self.history.append(entry)
        self._save()

    def get_current_elo(self, version: str) -> float:
        """Get the current ELO for a playbook version."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                return entry["elo"]
        return self.elo_system.initial_elo

    def record_matchup(self, version_a: str, version_b: str, winner: str) -> Tuple[float, float]:
        """Record a match between two playbook versions. Returns (new_elo_a, new_elo_b)."""
        elo_a = self.get_current_elo(version_a)
        elo_b = self.get_current_elo(version_b)

        if winner == version_a:
            new_a, new_b = self.elo_system.update_elo(elo_a, elo_b)
        elif winner == version_b:
            new_b, new_a = self.elo_system.update_elo(elo_b, elo_a)
        else:
            raise ValueError(f"Winner must be one of the two versions: {version_a} or {version_b}")

        self._update_entry(version_a, new_a, version_a == winner)
        self._update_entry(version_b, new_b, version_b == winner)

        return new_a, new_b

    def _update_entry(self, version: str, new_elo: float, won: bool) -> None:
        """Update a single entry in history."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                entry["elo"] = new_elo
                entry["matches_played"] += 1
                if won:
                    entry["matches_won"] += 1
                entry["timestamp"] = time.time()
                break
        else:
            self.register_playbook(version, new_elo)
            for entry in reversed(self.history):
                if entry["version"] == version:
                    entry["matches_played"] = 1
                    if won:
                        entry["matches_won"] = 1
                    break
        self._save()

    def get_elo_history(self) -> List[Dict]:
        """Return full ELO history for plotting."""
        return self.history

    def get_current_champion(self) -> str:
        """Return the version with the highest ELO."""
        if not self.history:
            return "none"
        return max(self.history, key=lambda x: x["elo"])["version"]

    def get_elo_curve_data(self) -> Dict:
        """Return data formatted for plotting: {versions: [], elos: [], timestamps: []}."""
        sorted_history = sorted(self.history, key=lambda x: x["timestamp"])
        return {
            "versions": [h["version"] for h in sorted_history],
            "elos": [h["elo"] for h in sorted_history],
            "timestamps": [h["timestamp"] for h in sorted_history],
            "matches_played": [h["matches_played"] for h in sorted_history],
            "matches_won": [h["matches_won"] for h in sorted_history]
        }


class ELOSystem:
    """Core ELO rating calculation system."""

    def __init__(self, k_factor: int = 32, initial_elo: float = 1000.0):
        self.k_factor = k_factor
        self.initial_elo = initial_elo

    def calculate_expected_score(self, elo_a: float, elo_b: float) -> float:
        """Calculate expected win probability for player A vs player B."""
        return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))

    def update_elo(self, winner_elo: float, loser_elo: float) -> Tuple[float, float]:
        """Update ELO ratings after a match. Returns (new_winner_elo, new_loser_elo)."""
        expected_winner = self.calculate_expected_score(winner_elo, loser_elo)
        expected_loser = 1.0 - expected_winner

        new_winner = winner_elo + self.k_factor * (1.0 - expected_winner)
        new_loser = loser_elo + self.k_factor * (0.0 - expected_loser)

        return round(new_winner, 2), round(new_loser, 2)


class PlaybookELOTracker:
    """Tracks ELO ratings for playbook versions with persistence."""

    def __init__(self, storage_path: str = "./elo_history/"):
        self.storage_path = storage_path
        self.elo_system = ELOSystem()
        self.history: List[Dict] = []
        os.makedirs(storage_path, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load ELO history from disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                self.history = json.load(f)

    def _save(self) -> None:
        """Save ELO history to disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        with open(history_file, "w") as f:
            json.dump(self.history, f, indent=2, default=str)

    def register_playbook(self, version: str, elo: float = 1000.0) -> None:
        """Register a new playbook version with initial ELO."""
        entry = {
            "version": version,
            "elo": elo,
            "timestamp": time.time(),
            "matches_played": 0,
            "matches_won": 0
        }
        self.history.append(entry)
        self._save()

    def get_current_elo(self, version: str) -> float:
        """Get the current ELO for a playbook version."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                return entry["elo"]
        return self.elo_system.initial_elo

    def record_matchup(self, version_a: str, version_b: str, winner: str) -> Tuple[float, float]:
        """Record a match between two playbook versions. Returns (new_elo_a, new_elo_b)."""
        elo_a = self.get_current_elo(version_a)
        elo_b = self.get_current_elo(version_b)

        if winner == version_a:
            new_a, new_b = self.elo_system.update_elo(elo_a, elo_b)
        elif winner == version_b:
            new_b, new_a = self.elo_system.update_elo(elo_b, elo_a)
        else:
            raise ValueError(f"Winner must be one of the two versions: {version_a} or {version_b}")

        self._update_entry(version_a, new_a, version_a == winner)
        self._update_entry(version_b, new_b, version_b == winner)

        return new_a, new_b

    def _update_entry(self, version: str, new_elo: float, won: bool) -> None:
        """Update a single entry in history."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                entry["elo"] = new_elo
                entry["matches_played"] += 1
                if won:
                    entry["matches_won"] += 1
                entry["timestamp"] = time.time()
                break
        else:
            self.register_playbook(version, new_elo)
            for entry in reversed(self.history):
                if entry["version"] == version:
                    entry["matches_played"] = 1
                    if won:
                        entry["matches_won"] = 1
                    break
        self._save()

    def get_elo_history(self) -> List[Dict]:
        """Return full ELO history for plotting."""
        return self.history

    def get_current_champion(self) -> str:
        """Return the version with the highest ELO."""
        if not self.history:
            return "none"
        return max(self.history, key=lambda x: x["elo"])["version"]

    def get_elo_curve_data(self) -> Dict:
        """Return data formatted for plotting: {versions: [], elos: [], timestamps: []}."""
        sorted_history = sorted(self.history, key=lambda x: x["timestamp"])
        return {
            "versions": [h["version"] for h in sorted_history],
            "elos": [h["elo"] for h in sorted_history],
            "timestamps": [h["timestamp"] for h in sorted_history],
            "matches_played": [h["matches_played"] for h in sorted_history],
            "matches_won": [h["matches_won"] for h in sorted_history]
        }


class ELOSystem:
    """Core ELO rating calculation system."""

    def __init__(self, k_factor: int = 32, initial_elo: float = 1000.0):
        self.k_factor = k_factor
        self.initial_elo = initial_elo

    def calculate_expected_score(self, elo_a: float, elo_b: float) -> float:
        """Calculate expected win probability for player A vs player B."""
        return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))

    def update_elo(self, winner_elo: float, loser_elo: float) -> Tuple[float, float]:
        """Update ELO ratings after a match. Returns (new_winner_elo, new_loser_elo)."""
        expected_winner = self.calculate_expected_score(winner_elo, loser_elo)
        expected_loser = 1.0 - expected_winner

        new_winner = winner_elo + self.k_factor * (1.0 - expected_winner)
        new_loser = loser_elo + self.k_factor * (0.0 - expected_loser)

        return round(new_winner, 2), round(new_loser, 2)


class PlaybookELOTracker:
    """Tracks ELO ratings for playbook versions with persistence."""

    def __init__(self, storage_path: str = "./elo_history/"):
        self.storage_path = storage_path
        self.elo_system = ELOSystem()
        self.history: List[Dict] = []
        os.makedirs(storage_path, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load ELO history from disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                self.history = json.load(f)

    def _save(self) -> None:
        """Save ELO history to disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        with open(history_file, "w") as f:
            json.dump(self.history, f, indent=2, default=str)

    def register_playbook(self, version: str, elo: float = 1000.0) -> None:
        """Register a new playbook version with initial ELO."""
        entry = {
            "version": version,
            "elo": elo,
            "timestamp": time.time(),
            "matches_played": 0,
            "matches_won": 0
        }
        self.history.append(entry)
        self._save()

    def get_current_elo(self, version: str) -> float:
        """Get the current ELO for a playbook version."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                return entry["elo"]
        return self.elo_system.initial_elo

    def record_matchup(self, version_a: str, version_b: str, winner: str) -> Tuple[float, float]:
        """Record a match between two playbook versions. Returns (new_elo_a, new_elo_b)."""
        elo_a = self.get_current_elo(version_a)
        elo_b = self.get_current_elo(version_b)

        if winner == version_a:
            new_a, new_b = self.elo_system.update_elo(elo_a, elo_b)
        elif winner == version_b:
            new_b, new_a = self.elo_system.update_elo(elo_b, elo_a)
        else:
            raise ValueError(f"Winner must be one of the two versions: {version_a} or {version_b}")

        self._update_entry(version_a, new_a, version_a == winner)
        self._update_entry(version_b, new_b, version_b == winner)

        return new_a, new_b

    def _update_entry(self, version: str, new_elo: float, won: bool) -> None:
        """Update a single entry in history."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                entry["elo"] = new_elo
                entry["matches_played"] += 1
                if won:
                    entry["matches_won"] += 1
                entry["timestamp"] = time.time()
                break
        else:
            self.register_playbook(version, new_elo)
            for entry in reversed(self.history):
                if entry["version"] == version:
                    entry["matches_played"] = 1
                    if won:
                        entry["matches_won"] = 1
                    break
        self._save()

    def get_elo_history(self) -> List[Dict]:
        """Return full ELO history for plotting."""
        return self.history

    def get_current_champion(self) -> str:
        """Return the version with the highest ELO."""
        if not self.history:
            return "none"
        return max(self.history, key=lambda x: x["elo"])["version"]

    def get_elo_curve_data(self) -> Dict:
        """Return data formatted for plotting: {versions: [], elos: [], timestamps: []}."""
        sorted_history = sorted(self.history, key=lambda x: x["timestamp"])
        return {
            "versions": [h["version"] for h in sorted_history],
            "elos": [h["elo"] for h in sorted_history],
            "timestamps": [h["timestamp"] for h in sorted_history],
            "matches_played": [h["matches_played"] for h in sorted_history],
            "matches_won": [h["matches_won"] for h in sorted_history]
        }


class ELOSystem:
    """Core ELO rating calculation system."""

    def __init__(self, k_factor: int = 32, initial_elo: float = 1000.0):
        self.k_factor = k_factor
        self.initial_elo = initial_elo

    def calculate_expected_score(self, elo_a: float, elo_b: float) -> float:
        """Calculate expected win probability for player A vs player B."""
        return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))

    def update_elo(self, winner_elo: float, loser_elo: float) -> Tuple[float, float]:
        """Update ELO ratings after a match. Returns (new_winner_elo, new_loser_elo)."""
        expected_winner = self.calculate_expected_score(winner_elo, loser_elo)
        expected_loser = 1.0 - expected_winner

        new_winner = winner_elo + self.k_factor * (1.0 - expected_winner)
        new_loser = loser_elo + self.k_factor * (0.0 - expected_loser)

        return round(new_winner, 2), round(new_loser, 2)


class PlaybookELOTracker:
    """Tracks ELO ratings for playbook versions with persistence."""

    def __init__(self, storage_path: str = "./elo_history/"):
        self.storage_path = storage_path
        self.elo_system = ELOSystem()
        self.history: List[Dict] = []
        os.makedirs(storage_path, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load ELO history from disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                self.history = json.load(f)

    def _save(self) -> None:
        """Save ELO history to disk."""
        history_file = os.path.join(self.storage_path, "elo_history.json")
        with open(history_file, "w") as f:
            json.dump(self.history, f, indent=2, default=str)

    def register_playbook(self, version: str, elo: float = 1000.0) -> None:
        """Register a new playbook version with initial ELO."""
        entry = {
            "version": version,
            "elo": elo,
            "timestamp": time.time(),
            "matches_played": 0,
            "matches_won": 0
        }
        self.history.append(entry)
        self._save()

    def get_current_elo(self, version: str) -> float:
        """Get the current ELO for a playbook version."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                return entry["elo"]
        return self.elo_system.initial_elo

    def record_matchup(self, version_a: str, version_b: str, winner: str) -> Tuple[float, float]:
        """Record a match between two playbook versions. Returns (new_elo_a, new_elo_b)."""
        elo_a = self.get_current_elo(version_a)
        elo_b = self.get_current_elo(version_b)

        if winner == version_a:
            new_a, new_b = self.elo_system.update_elo(elo_a, elo_b)
        elif winner == version_b:
            new_b, new_a = self.elo_system.update_elo(elo_b, elo_a)
        else:
            raise ValueError(f"Winner must be one of the two versions: {version_a} or {version_b}")

        self._update_entry(version_a, new_a, version_a == winner)
        self._update_entry(version_b, new_b, version_b == winner)

        return new_a, new_b

    def _update_entry(self, version: str, new_elo: float, won: bool) -> None:
        """Update a single entry in history."""
        for entry in reversed(self.history):
            if entry["version"] == version:
                entry["elo"] = new_elo
                entry["matches_played"] += 1
                if won:
                    entry["matches_won"] += 1
                entry["timestamp"] = time.time()
                break
        else:
            self.register_playbook(version, new_elo)
            for entry in reversed(self.history):
                if entry["version"] == version:
                    entry["matches_played"] = 1
                    if won:
                        entry["matches_won"] = 1
                    break
        self._save()

    def get_elo_history(self) -> List[Dict]:
        """Return full ELO history for plotting."""
        return self.history

    def get_current_champion(self) -> str:
        """Return the version with the highest ELO."""
        if not self.history:
            return "none"
        return max(self.history, key=lambda x: x["elo"])["version"]

    def get_elo_curve_data(self) -> Dict:
        """Return data formatted for plotting: {versions: [], elos: [], timestamps: []}."""
        sorted_history = sorted(self.history, key=lambda x: x["timestamp"])
        return {
            "versions": [h["version"] for h in sorted_history],
            "elos": [h["elo"] for h in sorted_history],
            "timestamps": [h["timestamp"] for h in sorted_history],
            "matches_played": [h["matches_played"] for h in sorted_history],
            "matches_won": [h["matches_won"] for h in sorted_history]
        }


def plot_elo_curve(history: List[Dict]) -> str:
    """Generate a dark-themed ELO curve plot and return as base64 PNG string.
    
    Args:
        history: List of ELO history entries with version, elo, timestamp keys
        
    Returns:
        Base64 encoded PNG image string
    """
    matplotlib.use('Agg')
    plt.style.use('dark_background')
    
    sorted_history = sorted(history, key=lambda x: x.get("timestamp", 0))
    
    versions = [h.get("version", "") for h in sorted_history]
    elos = [h.get("elo", 1000) for h in sorted_history]
    
    fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1a1a2e')
    ax.set_facecolor('#1a1a2e')
    
    ax.plot(range(len(elos)), elos, color='#00ff88', linewidth=2, marker='o', 
            markersize=8, markerfacecolor='#00ff88', markeredgecolor='white', markeredgewidth=1)
    
    for i, (v, e) in enumerate(zip(versions, elos)):
        ax.annotate(v, (i, e), textcoords="offset points", xytext=(0, 15),
                    ha='center', fontsize=9, color='white', fontweight='bold')
    
    ax.set_xlabel('Match Number', color='white', fontsize=12, fontweight='bold')
    ax.set_ylabel('ELO Rating', color='white', fontsize=12, fontweight='bold')
    ax.set_title('🧬 Playbook ELO Evolution', color='#00ff88', fontsize=14, fontweight='bold')
    
    ax.tick_params(axis='x', colors='white', labelsize=10)
    ax.tick_params(axis='y', colors='white', labelsize=10)
    ax.grid(True, alpha=0.3, color='gray', linestyle='--')
    
    ax.spines['bottom'].set_color('white')
    ax.spines['top'].set_color('white')
    ax.spines['right'].set_color('white')
    ax.spines['left'].set_color('white')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()
    buf.seek(0)
    
    return base64.b64encode(buf.read()).decode('utf-8')
