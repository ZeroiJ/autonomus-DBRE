---
title: Autonomic DBRE
emoji: 🧠
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
suggested_hardware: t4-small
---

# 🧠 Autonomic DBRE — Self-Improving Database Agent

A self-healing database reliability engineer that diagnoses slow queries, fixes them, and rewrites its own diagnostic playbook using metacognitive self-modification and ELO-based evolution.

## Features
- **Self-Improving**: Meta Agent rewrites the diagnostic playbook after every 5 episodes
- **ELO Evolution**: Playbook versions compete — best strategy survives
- **4 Reward Functions**: Correctness, Efficiency, Style, Anticheat
- **Schema Drift**: Random database mutations simulate production chaos
- **Real PostgreSQL**: Live EXPLAIN ANALYZE, index creation, query rewriting

## Architecture
Task Agent solves queries → Meta Agent watches → Rewrites playbook → ELO ranks versions → Champion emerges

## Tech Stack
Qwen2.5-Coder-1.5B + GRPO + OpenEnv + PostgreSQL + Gradio

## Local Setup
```bash
pip install -r requirements.txt
docker run --name dbre-postgres -e POSTGRES_USER=dbre_admin -e POSTGRES_PASSWORD=dbre_pass -e POSTGRES_DB=dbre -p 5432:5432 -d postgres:16-alpine
uvicorn server.app:app --host 0.0.0.0 --port 8000 &
DB_USER=dbre_admin DB_PASSWORD=dbre_pass python3 app.py
```

## Project Structure
```
.
├── dbre/                      # Core database reliability engine
│   ├── __init__.py
│   ├── database.py            # PostgreSQL connection & schema
│   ├── workload_generator.py  # 6 broken query patterns
│   ├── schema_drift.py        # 6 mutation types
│   ├── holdout_queries.py     # 20 test cases
│   ├── playbook.py            # Playbook management
│   ├── elo_system.py          # ELO rating & visualization
│   ├── meta_agent.py          # Self-improving meta agent
│   ├── environment.py         # OpenEnv interface
│   └── rewards/               # Reward functions
│       ├── __init__.py
│       ├── correctness.py
│       ├── efficiency.py
│       ├── style.py
│       └── anticheat.py
├── server/                    # FastAPI backend
│   ├── __init__.py
│   └── app.py
├── app.py                     # Gradio dashboard
├── train.py                   # Training loop (500 episodes)
├── requirements.txt           # 29 Python dependencies
├── Dockerfile                 # Container configuration
├── openenv.yaml               # OpenEnv specification
├── CHANGELOG.md               # Detailed change history
└── README.md                  # This file
```

## How It Works

1. **Episode Start**: Environment generates a broken query with schema drift
2. **Agent Action**: LLM (Qwen2.5-Coder) suggests fixes via actions
3. **Reward Calculation**: 4 metrics evaluate the fix quality
4. **Episode End**: Meta Agent observes outcome after 5 episodes
5. **Playbook Evolution**: Meta generates diff, ELO ranks versions, champion emerges
6. **Dashboard**: Real-time visualization of ELO curve, rewards, query fixes

## License
MIT

## Author
DBRE Team

## Acknowledgments
- OpenAI for Gymnasium interface
- HuggingFace for Transformers and Spaces
- PostgreSQL for robust database engine
- Gradio for beautiful dashboard UI

---

## 📋 Hackathon Submission Links

| Requirement | Link |
|-------------|------|
| **Live Environment (HF Space)** | [autonomic-dbre](https://huggingface.co/spaces/ZeroiJ/autonomic-dbre) |
| **Blog Post** | [Blog.md](https://huggingface.co/spaces/ZeroiJ/autonomic-dbre/blob/main/Blog.md) |
| **Training Notebook (Colab)** | [training_notebook.ipynb](https://github.com/ZeroiJ/autonomus-DBRE/blob/main/training_notebook.ipynb) |
| **GitHub Repository** | [autonomus-DBRE](https://github.com/ZeroiJ/autonomus-DBRE) |
| **Trained Model Weights** | [dbre_trained/](https://github.com/ZeroiJ/autonomus-DBRE/tree/main/dbre_trained) |

## 📊 Training Evidence

- **Method:** GRPO (Group Relative Policy Optimization) via HuggingFace TRL
- **Model:** Qwen2.5-Coder-1.5B-Instruct (4-bit QLoRA)
- **Steps:** 500 | **Learning Rate:** 5e-5
- **Reward Curve:** Rewards climbed from 0.02 → 0.35+ over training
- **ELO Evolution:** v1 (984) → v2 (999) → v3 (1016.7) — champion emerged autonomously

## 🎥 Demo

[Live Dashboard](https://huggingface.co/spaces/ZeroiJ/autonomic-dbre) — Click "Inject Database Chaos" to see the agent fix a broken query in real-time.
