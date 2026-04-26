# Changelog — Autonomic DBRE

## v0.3.0 — Meta Agent & ELO Evolution (April 25, 2026 - Evening)

### Added
- Meta Agent that observes episodes and generates playbook diffs
- ELO-based versioning system for playbook evolution
- Holdout evaluation with rule-coverage scoring
- Auto-trigger: Meta Agent fires every 5 episodes automatically
- Verified self-improvement loop: v1 → v2 → v3 champion

### Fixed
- Circular import in meta_agent.py (was importing itself)
- Database corruption from schema drift (seed_data now drops and rebuilds)
- Anticheat reward returning 0.5 (fixed import chain in rewards/__init__.py)
- Correctness reward now receives new_rows from environment
- SchemaDrifter transaction rollback on failed mutations
- Duplicate v1 ELO registrations on every reset

### Changed
- evaluate_playbook: switched from 15-hard-queries to 7-rule coverage check
- seed_data: drops all tables and recreates before seeding (drift-safe)
- episode termination: lowered max_steps threshold for faster meta cycles

## v0.2.0 — Core Environment (April 25, 2026 - Afternoon)

### Added
- DBREEnvironment with Gymnasium/OpenEnv interface (reset, step, state)
- 4 independent reward functions: correctness, efficiency, style, anticheat
- Weighted total reward: 0.4×correctness + 0.3×efficiency + 0.2×style + 0.1×anticheat
- PostgreSQL database handler with 5 tables, 100/50/300/600/200 seed data
- WorkloadGenerator: 6 broken query patterns (N+1, missing index, bad join, etc.)
- SchemaDrifter: 5 mutation types simulating production drift
- FastAPI server (server/app.py) with /reset, /step, /state, /elo_history endpoints
- Gradio dashboard with dark theme, chaos inject button, reward bars, ELO chart
- PlaybookManager with unified diff apply/archive/revert

### Fixed
- PostgreSQL port conflict (Docker container reuse)
- Missing faker dependency in requirements.txt
- Database connection defaults aligned with dbre_admin/dbre_pass credentials

## v0.1.0 — Project Scaffold (April 25, 2026 - Morning)

### Added
- Project structure: dbre/, server/, rewards/ module layout
- requirements.txt with all dependencies
- Dockerfile for HuggingFace Spaces deployment
- openenv.yaml environment manifest
- Default diagnostic playbook (6 priority rules)
- Holdout query set (20 queries for meta evaluation)
- Train.py baseline training loop (500 episodes, checkpoint saving)
