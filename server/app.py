from __future__ import annotations

import asyncio
import functools
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dbre.environment import DBREAction, DBREEnvironment
from dbre.inference import ModelLoadError, default_adapter_dir, load_optimizer_model
from dbre.optimizer import optimize_sql


env_instance: DBREEnvironment | None = None

BASE_MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global env_instance
    env_instance = DBREEnvironment(config={"max_steps": 20, "latency_threshold_pct": 0.6})
    app.state.model = None
    app.state.tokenizer = None
    app.state.model_error = None
    app.state.model_load_attempted = False
    app.state.adapter_path = str(default_adapter_dir())
    yield
    if env_instance and env_instance.db and env_instance.db.conn:
        env_instance.db.close()


app = FastAPI(title="DBRE API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OptimizeRequest(BaseModel):
    query: str = Field(..., min_length=1, description="SQL query to optimize")


async def _ensure_model(request: Request) -> tuple[Any, Any]:
    """Lazy-load Qwen + LoRA once per process."""
    st = request.app.state
    if st.model is not None and st.tokenizer is not None:
        return st.model, st.tokenizer
    if st.model_load_attempted and st.model_error:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "model_not_loaded",
                "message": st.model_error,
                "hint": "Train with train.py / run_experiment.py or set DBRE_ADAPTER_DIR.",
            },
        )
    st.model_load_attempted = True
    loop = asyncio.get_running_loop()
    try:
        model, tokenizer = await loop.run_in_executor(None, load_optimizer_model)
    except ModelLoadError as e:
        st.model_error = str(e)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "model_not_loaded",
                "message": str(e),
                "hint": "Provide adapter_config.json under dbre_trained (or DBRE_ADAPTER_DIR).",
            },
        ) from e
    except Exception as e:
        st.model_error = str(e)
        raise HTTPException(
            status_code=503,
            detail={"error": "model_load_failed", "message": str(e)},
        ) from e
    st.model = model
    st.tokenizer = tokenizer
    st.model_error = None
    return model, tokenizer


@app.post("/reset", response_model=dict)
async def reset_environment() -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(
            status_code=503,
            detail={"error": "environment_unavailable", "message": "Environment not initialized"},
        )

    observation = env_instance.reset()

    return {
        "observation": observation.model_dump(),
        "info": {},
    }


@app.post("/step", response_model=dict)
async def step_environment(action_data: dict) -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(
            status_code=503,
            detail={"error": "environment_unavailable", "message": "Environment not initialized"},
        )

    try:
        action = DBREAction(**action_data)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_action", "message": str(e)},
        ) from e

    observation, reward, terminated, info = env_instance.step(action)
    truncated = False

    return {
        "observation": observation.model_dump(),
        "reward": reward,
        "terminated": terminated,
        "truncated": truncated,
        "info": info,
    }


@app.get("/state", response_model=dict)
async def get_state() -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(status_code=503, detail={"error": "environment_unavailable"})

    observation = env_instance.state()

    return {
        "observation": observation.model_dump(),
    }


@app.get("/elo_history", response_model=dict)
async def get_elo_history() -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(status_code=503, detail={"error": "environment_unavailable"})

    history = env_instance.elo_tracker.get_elo_history()

    return {
        "history": history,
    }


@app.get("/current_playbook", response_model=dict)
async def get_current_playbook() -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(status_code=503, detail={"error": "environment_unavailable"})

    playbook = env_instance.playbook_manager.get_current()

    return {
        "playbook": playbook,
    }


@app.get("/api/v1/health")
async def api_v1_health(request: Request) -> dict[str, Any]:
    db_ok = bool(env_instance and env_instance.db.conn)
    db_detail = "connected" if db_ok else "unavailable"
    model_ready = getattr(request.app.state, "model", None) is not None
    payload: dict[str, Any] = {
        "status": "ok" if db_ok else "degraded",
        "database": db_detail,
        "model": "loaded" if model_ready else "not_loaded",
        "base_model": BASE_MODEL_ID,
        "adapter_path": getattr(request.app.state, "adapter_path", str(default_adapter_dir())),
    }
    err = getattr(request.app.state, "model_error", None)
    if err and not model_ready:
        payload["model_error"] = err
    return payload


@app.post("/api/v1/optimize")
async def api_v1_optimize(request: Request, body: OptimizeRequest) -> dict[str, Any]:
    if not env_instance or not env_instance.db.conn:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "database_unavailable",
                "message": "PostgreSQL connection is not available.",
            },
        )

    model, tokenizer = await _ensure_model(request)

    loop = asyncio.get_running_loop()
    outcome = await loop.run_in_executor(
        None,
        functools.partial(
            optimize_sql,
            env_instance.db.conn,
            body.query,
            model,
            tokenizer,
            include_explain_text=False,
        ),
    )

    if outcome.error:
        detail: dict[str, Any] = {
            "error": "optimization_failed",
            "message": outcome.error,
            "original": outcome.original,
        }
        if "Invalid SQL" in outcome.error or "execution error on original" in outcome.error:
            raise HTTPException(status_code=400, detail=detail) from None
        if "Model generation" in outcome.error:
            raise HTTPException(status_code=502, detail=detail) from None
        if "Optimized SQL failed" in outcome.error:
            raise HTTPException(status_code=422, detail=detail) from None
        raise HTTPException(status_code=400, detail=detail) from None

    return {
        "original": outcome.original,
        "optimized": outcome.optimized,
        "baseline_latency_ms": outcome.baseline_latency_ms,
        "optimized_latency_ms": outcome.optimized_latency_ms,
        "improvement_pct": outcome.improvement_pct,
        "reward_breakdown": outcome.reward_breakdown,
        "explain_summary": outcome.explain_summary,
    }


@app.post("/train")
def start_training() -> dict[str, str]:
    import subprocess

    subprocess.Popen(["python3", "train.py"])
    return {"status": "training started"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
