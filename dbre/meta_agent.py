from __future__ import annotations

from typing import Dict, Any, List

from dbre.playbook import PlaybookManager
from dbre.elo_system import PlaybookELOTracker
from dbre.holdout_queries import evaluate_playbook


class MetaAgent:
    """Watches episodes and rewrites the diagnostic playbook based on outcomes."""

    def __init__(
        self,
        playbook_manager: PlaybookManager,
        elo_tracker: PlaybookELOTracker,
        episode_history_limit: int = 5
    ) -> None:
        self.playbook_manager = playbook_manager
        self.elo_tracker = elo_tracker
        self.episode_history_limit = episode_history_limit
        self.episode_history: List[Dict[str, Any]] = []
        self.current_version = 1

    def observe_episode(self, episode_data: Dict[str, Any]) -> None:
        self.episode_history.append(episode_data)
        if len(self.episode_history) > self.episode_history_limit * 2:
            self.episode_history = self.episode_history[-self.episode_history_limit * 2:]

    def should_trigger(self) -> bool:
        return len(self.episode_history) > 0 and len(self.episode_history) % self.episode_history_limit == 0

    def generate_playbook_diff(self) -> str:
        if len(self.episode_history) < self.episode_history_limit:
            return ""

        recent = self.episode_history[-self.episode_history_limit:]
        successes = [e for e in recent if e.get("total_reward", 0) >= 0.6]
        failures = [e for e in recent if e.get("total_reward", 0) < 0.6]
        failure_reasons = [e.get("failure_reason", "unknown") for e in failures]
        success_patterns = [e.get("pattern", "unknown") for e in successes]

        diff_lines = ["# Playbook Update", "", f"## Version {self.current_version + 1}", ""]

        if "efficiency" in failure_reasons:
            diff_lines.append("### Efficiency Rules")
            diff_lines.append("- Always check EXPLAIN ANALYZE before rewriting")
            diff_lines.append("- Add index if sequential scan detected")
            diff_lines.append("")

        if "incorrectness" in failure_reasons:
            diff_lines.append("### Correctness Rules")
            diff_lines.append("- Verify row counts match original query")
            diff_lines.append("")

        if success_patterns:
            diff_lines.append("### Successful Patterns (Prioritize)")
            for p in set(success_patterns):
                diff_lines.append(f"- Pattern '{p}' was successful — keep using it")
            diff_lines.append("")

        return "\n".join(diff_lines)

    def evaluate_and_commit(self, connection) -> Dict[str, Any]:
        if not self.should_trigger():
            return {"accepted": False, "reason": "Not enough episodes yet"}

        diff = self.generate_playbook_diff()
        if not diff:
            return {"accepted": False, "reason": "No diff generated"}

        try:
            new_version = self.playbook_manager.apply_diff(diff)
        except Exception as e:
            return {"accepted": False, "reason": f"Diff failed: {e}"}

        old_ver = f"v{self.current_version}"
        new_ver = f"v{self.current_version + 1}"
        self.elo_tracker.register_playbook(new_ver, 1000)

        try:
            score = evaluate_playbook(connection, new_version)
            if score > 0.5:
                self.elo_tracker.record_matchup(old_ver, new_ver, new_ver)
                self.current_version += 1
                return {"accepted": True, "new_elo": self.elo_tracker.get_current_elo(new_ver), "holdout_score": score}
            else:
                self.playbook_manager.revert_to_version(old_ver)
                self.elo_tracker.record_matchup(old_ver, new_ver, old_ver)
                return {"accepted": False, "reason": f"Score {score:.2f} too low"}
        except Exception as e:
            self.playbook_manager.revert_to_version(old_ver)
            return {"accepted": False, "reason": str(e)}
