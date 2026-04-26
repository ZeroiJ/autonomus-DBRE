from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dbre.environment import DBREAction, DBREEnvironment, DBREObservation


env_instance: DBREEnvironment | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global env_instance
    env_instance = DBREEnvironment(config={"max_steps": 20, "latency_threshold_pct": 0.6})
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "type": type(exc).__name__,
        },
    )


@app.post("/reset", response_model=dict)
async def reset_environment() -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(status_code=503, detail="Environment not initialized")

    observation, info = env_instance.reset()

    return {
        "observation": observation.dict(),
        "info": info,
    }


@app.post("/step", response_model=dict)
async def step_environment(action_data: dict) -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(status_code=503, detail="Environment not initialized")

    try:
        action = DBREAction(**action_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid action: {str(e)}")

    observation, reward, terminated, truncated, info = env_instance.step(action)

    return {
        "observation": observation.dict(),
        "reward": reward,
        "terminated": terminated,
        "truncated": truncated,
        "info": info,
    }


@app.get("/state", response_model=dict)
async def get_state() -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(status_code=503, detail="Environment not initialized")

    observation = env_instance.state()

    return {
        "observation": observation.dict(),
    }


@app.get("/elo_history", response_model=dict)
async def get_elo_history() -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(status_code=503, detail="Environment not initialized")

    history = env_instance.elo_tracker.get_elo_history()

    return {
        "history": history,
    }


@app.get("/current_playbook", response_model=dict)
async def get_current_playbook() -> dict[str, Any]:
    if not env_instance:
        raise HTTPException(status_code=503, detail="Environment not initialized")

    playbook = env_instance.playbook_manager.get_current()

    return {
        "playbook": playbook,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


@app.post("/train")
def start_training():
    import subprocess
    subprocess.Popen(["python3", "train.py"])
    return {"status": "training started"}