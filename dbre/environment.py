from __future__ import annotations

import time
import uuid
from typing import Dict, Any, Optional, Tuple

from pydantic import BaseModel, Field

from dbre.database import DBREPostgres
from dbre.procedural_workload import ProceduralWorkloadGenerator
from dbre.schema_drift import SchemaDrifter
from dbre.playbook import PlaybookManager
from dbre.meta_agent import MetaAgent
from dbre.elo_system import PlaybookELOTracker
from dbre.rewards import compute_total_reward


class DBREObservation(BaseModel):
    episode_id: str
    broken_query: str
    schema_description: str = ""
    schema_diff: list[str] = Field(default_factory=list)
    execution_trace: dict = Field(default_factory=dict)
    agent_playbook: str = ""
    baseline_latency_ms: float = 0.0
    current_score: float = 0.0
    attempts: int = 0
    max_attempts: int = 20


class DBREAction(BaseModel):
    action_type: str = Field(..., description="One of: rewrite_query, add_index, commit_playbook_diff")
    new_sql: Optional[str] = None
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    diff: Optional[str] = None


class DBREEnvironment:
    """OpenEnv-compatible environment for Autonomic DBRE."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.max_steps = config.get("max_steps", 20)
        self.latency_threshold_pct = config.get("latency_threshold_pct", 0.6)

        self.db = DBREPostgres()
        self.db.connect()
        self.db.create_tables()
        self.db.seed_data()

        self.workload_gen = ProceduralWorkloadGenerator(self.db.conn)
        self.schema_drifter = SchemaDrifter(self.db.conn)
        self.playbook_manager = PlaybookManager()
        self.elo_tracker = PlaybookELOTracker()
        self.meta_agent = MetaAgent(self.playbook_manager, self.elo_tracker, episode_history_limit=5)

        self.episode_id: str = ""
        self.broken_query: str = ""
        self.reference_rows: list = []
        self.baseline_latency_ms: float = 0.0
        self.current_optimized_query: str = ""
        self.attempts: int = 0
        self.episode_done: bool = False
        self.episode_success: bool = False

        # v1 registered once at init
        if not self.elo_tracker.history:
            self.elo_tracker.register_playbook("v1", 1000)

    def reset(self) -> DBREObservation:
        """Reset environment for a new episode."""
        self.schema_drifter.apply_random_drift()
        self.broken_query, self.baseline_latency_ms = self.workload_gen.generate_broken_query()
        self.reference_rows = self.workload_gen.get_expected_rows(self.broken_query)

        self.episode_id = str(uuid.uuid4())[:8]
        self.attempts = 0
        self.episode_done = False
        self.episode_success = False
        self.current_optimized_query = ""

        return DBREObservation(
            episode_id=self.episode_id,
            broken_query=self.broken_query,
            schema_description=self._get_schema_description(),
            schema_diff=self.schema_drifter.get_schema_diff(),
            execution_trace={},
            agent_playbook=self.playbook_manager.get_current(),
            baseline_latency_ms=self.baseline_latency_ms,
            current_score=0.0,
            attempts=0,
            max_attempts=self.max_steps
        )

    def step(self, action: DBREAction) -> Tuple[DBREObservation, float, bool, Dict[str, Any]]:
        """Execute an action and return (observation, reward, terminated, info)."""
        self.attempts += 1

        try:
            if action.action_type == "rewrite_query":
                reward_info = self._handle_rewrite_query(action.new_sql)
            elif action.action_type == "add_index":
                reward_info = self._handle_add_index(action.table_name, action.column_name)
            elif action.action_type == "commit_playbook_diff":
                reward_info = self._handle_playbook_diff(action.diff)
            else:
                reward_info = {"total": 0.0, "error": f"Unknown action_type: {action.action_type}"}
        except Exception as e:
            reward_info = {"total": 0.0, "error": str(e)}

        total_reward = reward_info.get("total", 0.0)

        if total_reward >= 0.6 or self.attempts >= self.max_steps:
            self.episode_done = True
            self.episode_success = total_reward >= 0.6
            self.meta_agent.observe_episode({
                "episode_id": self.episode_id,
                "success": self.episode_success,
                "total_reward": total_reward,
                "reward_breakdown": reward_info,
                "attempts": self.attempts
            })
            # Auto-trigger meta agent when it's ready
            if self.meta_agent.should_trigger():
                print("[META] Triggering playbook evaluation...")
                meta_result = self.meta_agent.evaluate_and_commit(self.db.conn)
                print(f"[META] Result: {meta_result}")

        observation = self._build_observation()
        info = {"reward_breakdown": reward_info, "episode_success": self.episode_success}

        return observation, total_reward, self.episode_done, info

    def state(self) -> DBREObservation:
        """Return current state without stepping."""
        return self._build_observation()

    def _handle_rewrite_query(self, new_sql: Optional[str]) -> Dict[str, Any]:
        """Handle a query rewrite action."""
        if not new_sql:
            return {"total": 0.0, "error": "No SQL provided"}

        try:
            cur = self.db.conn.cursor()
            cur.execute(new_sql)
            new_rows = cur.fetchall()
            cur.close()
            new_latency = self.workload_gen.measure_latency(self.db.conn, new_sql)
        except Exception as e:
            return {"total": 0.0, "error": f"SQL execution error: {str(e)}"}

        self.current_optimized_query = new_sql
        return compute_total_reward(
            original_query=self.broken_query,
            new_query=new_sql,
            reference_rows=self.reference_rows,
            baseline_latency_ms=self.baseline_latency_ms,
            new_latency_ms=new_latency,
            new_rows=new_rows
        )

    def _handle_add_index(self, table_name: Optional[str], column_name: Optional[str]) -> Dict[str, Any]:
        """Handle an add_index action."""
        if not table_name or not column_name:
            return {"total": 0.0, "error": "table_name and column_name required"}

        try:
            cursor = self.db.conn.cursor()
            index_name = f"idx_{table_name}_{column_name}"
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})")
            self.db.conn.commit()
            cursor.close()
        except Exception as e:
            return {"total": 0.0, "error": f"Index creation error: {str(e)}"}

        if self.current_optimized_query:
            try:
                new_latency = self.workload_gen.measure_latency(self.db.conn, self.current_optimized_query)
                return compute_total_reward(
                    original_query=self.broken_query,
                    new_query=self.current_optimized_query,
                    reference_rows=self.reference_rows,
                    baseline_latency_ms=self.baseline_latency_ms,
                    new_latency_ms=new_latency
                )
            except Exception:
                pass

        return {"total": 0.1, "note": "Index created but no query to evaluate yet"}

    def _handle_playbook_diff(self, diff: Optional[str]) -> Dict[str, Any]:
        """Handle a commit_playbook_diff action."""
        if not diff:
            return {"total": 0.0, "error": "No diff provided"}

        try:
            result = self.meta_agent.evaluate_and_commit(self.db.conn)
            if result["accepted"]:
                return {"total": 0.3, "note": f"Playbook updated. New ELO: {result['new_elo']}"}
            else:
                return {"total": 0.0, "note": "Playbook not accepted"}
        except Exception as e:
            return {"total": 0.0, "error": f"Playbook update error: {str(e)}"}

    def _build_observation(self) -> DBREObservation:
        """Build current observation."""
        return DBREObservation(
            episode_id=self.episode_id,
            broken_query=self.broken_query,
            schema_description=self._get_schema_description(),
            schema_diff=self.schema_drifter.get_schema_diff(),
            execution_trace={},
            agent_playbook=self.playbook_manager.get_current(),
            baseline_latency_ms=self.baseline_latency_ms,
            current_score=0.0,
            attempts=self.attempts,
            max_attempts=self.max_steps
        )

    def _get_schema_description(self) -> str:
        """Get human-readable schema description."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return f"Tables: {', '.join(tables)}"
        except Exception:
            return "Schema unavailable"
