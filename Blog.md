# We Built a Database Agent That Rewrites Its Own Brain — Here's What Broke Along the Way

**Meta PyTorch OpenEnv Hackathon Finale — April 25-26, 2026**

**Team:** Sujal Birwadkar & Yash Balpande

---

## The 48-Hour Reality

48 hours. Two people. One PostgreSQL database. And a self-improving agent that needed to train, evolve, and demo — all while running on hardware we didn't have.

We burned through $30 in HuggingFace compute credits. Our Colab GPU ran out mid-training. The Docker build failed six times on HF Spaces. At 3 AM, we discovered the model was generating SQL for tables that didn't exist. At 9 AM, all rewards were zero because we forgot to tell the model what our database looked like.

But at 1:30 PM on submission day, the agent's diagnostic playbook evolved from v1 (ELO 984) to v3 (ELO 1016.7) — completely autonomously. It wrote rules we never gave it.

This is the story of what we built, what broke, and why self-improving database agents matter.

---

## Why Databases?

Every production database breaks in ways nobody anticipates. A query runs fine for months, then suddenly takes 8 seconds. Not because the data changed — because someone renamed a column during a migration at 2 AM. An index got dropped. The query planner chose a join order that made sense at 10,000 rows but falls apart at 10 million.

We've both been on-call. We know the pain of diagnosing a slow query at 3 AM when the DBA who wrote the indexing strategy left the company six months ago. Traditional tools are static — tuned once, never learning from what actually happens in production. We wanted to build something that gets smarter every time it fixes something.

---

## What We Built

**Autonomic DBRE** is a reinforcement learning environment where an AI agent lives inside a PostgreSQL database and learns to fix slow queries. But the real innovation isn't the query fixing — it's the **meta-agent that rewrites the agent's own diagnostic playbook**.

Here's the loop:

1. **Inject chaos.** A random schema drift hits the database — columns disappear, indexes vanish, constraints break. A slow, broken query gets injected into the workload.

2. **Diagnose.** The agent reads `EXPLAIN ANALYZE` output — the same traces a human DBA uses. Sequential scans, hash join vs nested loop decisions, buffer hit ratios.

3. **Fix.** The agent rewrites the query, adds an index, or forces a different join order. It tests its fix and measures the latency.

4. **Score.** Four independent reward functions grade the fix: correctness (did it return the right rows?), efficiency (how much faster?), style (is the SQL clean?), and anticheat (is the agent trying to cheat by submitting empty queries?).

5. **Self-improve.** Every 5 episodes, a Meta Agent reviews what worked and what failed. It writes a code diff that updates the diagnostic playbook — the rules that control how the agent approaches problems. New rules get added. Failed strategies get deprioritized.

6. **Evolve.** The new playbook is tested against a hidden set of queries the agent has never seen. If it performs better, it becomes the active playbook. If not, it's discarded. ELO ratings track which version is the champion.

---

## The Evolution We Watched Happen

We started with a hand-written playbook v1 (ELO 984). Basic rules like "check for SELECT *" and "verify row counts."

After 5 episodes, the Meta Agent noticed that most failures came from missing indexes. It **rewrote the playbook** to add: "Always check EXPLAIN ANALYZE for sequential scans before attempting query rewrites." v2 (ELO 999) was born.

After 10 more episodes, v2 lost to v3 (ELO 1016.7), which had autonomously added: "Prioritize hash joins over nested loops for datasets larger than 1000 rows" and "Check for correlated subqueries before checking join order."

**We didn't write those rules. The agent did.**

---

## The Reward System

Instead of hand-crafted partial credit, we used strict binary rewards where possible:

| Reward | Weight | What It Checks |
|--------|--------|----------------|
| Correctness | 40% | Row-level comparison against reference output |
| Efficiency | 30% | (baseline_latency − new_latency) / baseline_latency |
| Style | 20% | No SELECT *, proper aliases, valid SQL |
| Anticheat | 10% | Blocks DROP, DELETE, TRUNCATE, empty queries |

The anticheat reward was crucial. Our first version gave partial credit for "close" answers, and the agent quickly learned to submit queries that were syntactically valid but semantically empty. Switching to strict binary anticheat eliminated this behavior entirely.

---

## Training: What Actually Worked

We fine-tuned **Qwen2.5-Coder-1.5B-Instruct** using GRPO (Group Relative Policy Optimization) with 4-bit QLoRA. Here's what the training journey actually looked like:

**Attempt 1:** Used Unsloth. Broke on Python 3.14. Abandoned.

**Attempt 2:** Colab T4 GPU. Ran out of compute credits mid-training. 3 hours wasted.

**Attempt 3:** HuggingFace Spaces with Docker. Build failed six times — missing faker, PostgreSQL auth errors, Dev Mode timeout. 4 hours of debugging.

**Attempt 4:** Local training on consumer GPU. Model loaded, training started, all rewards were zero. Discovered the model was generating SQL for fictional tables like `table_name` and `condition = 'value'`.

**Attempt 5 (the winner):** Added the actual database schema to the prompt. Rewards climbed from 0.02 → 0.35 over 500 steps. Training completed at 1:30 PM on submission day.

**Final config:** 500 GRPO steps, batch size 2, gradient accumulation 8, learning rate 5e-5, QLoRA rank 16 on attention projections. Training time: ~3.5 hours on a single GPU.

---

## Cost Breakdown

| Item | Cost |
|------|------|
| HuggingFace compute credits (T4 medium + A10G small) | $30 |
| Colab GPU runtime (exhausted) | Free tier |
| Local GPU electricity (overnight training) | ~$0.50 |
| HuggingFace PRO subscription (for SSH debugging) | $9 |
| Coffee | Dangerously high |
| Sleep | Negative 4 hours |

---

## What We Learned

**Self-improvement is non-monotonic.** The v2 playbook was sometimes worse than v1. It took multiple evolutionary cycles before v3 emerged as champion. Progress looked like stairs, not a smooth curve.

**Reward design is everything.** Our first reward function rewarded "trying hard." The agent learned to generate verbose, syntactically valid SQL that looked good but did nothing useful. Binary rewards for cheating changed the behavior immediately.

**Schema context matters.** The biggest single improvement came from adding the database schema to the training prompt. Before: 0.000 reward. After: 0.025 → 0.35 and climbing.

**Docker is the hardest part of AI deployment.** We spent more time debugging PostgreSQL auth in Docker than writing the actual reinforcement learning code.

---

## Live Demo

**[Launch Dashboard](https://huggingface.co/spaces/ZeroiJ/autonomic-dbre)** — Click "Inject Database Chaos" and watch the agent fix it live.

**[GitHub Repo](https://github.com/ZeroiJ/autonomus-DBRE)** — Full source code, trained model weights, and training logs.

---

## Built With

PyTorch · HuggingFace TRL · OpenEnv · Qwen2.5-Coder · PostgreSQL · Gradio · A lot of stubbornness

---

*Submitted April 26, 2026 for the Meta PyTorch OpenEnv Hackathon at Scaler School of Technology, Bangalore.*
