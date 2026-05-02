from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Tuple

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from dbre.prompts import SCHEMA_OPTIMIZATION_PROMPT

BASE_MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


class ModelLoadError(RuntimeError):
    """Raised when the optimizer model or adapter cannot be loaded."""


def default_adapter_dir() -> Path:
    return Path(os.environ.get("DBRE_ADAPTER_DIR", "dbre_trained")).resolve()


def load_optimizer_model(
    adapter_dir: str | Path | None = None,
    *,
    base_model_id: str = BASE_MODEL_ID,
    device_map: str | None = "auto",
) -> Tuple[Any, Any]:
    """Load Qwen2.5-Coder base (4-bit) + LoRA adapter from ``adapter_dir``."""
    adapter_path = Path(adapter_dir or default_adapter_dir()).resolve()
    cfg = adapter_path / "adapter_config.json"
    if not cfg.is_file():
        raise ModelLoadError(
            f"No LoRA adapter at {adapter_path} (expected adapter_config.json). "
            "Train with train.py / run_experiment.py or set DBRE_ADAPTER_DIR."
        )

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb,
        device_map=device_map,
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, str(adapter_path))
    model.eval()

    tok_path = adapter_path if (adapter_path / "tokenizer_config.json").is_file() else Path(base_model_id)
    tokenizer = AutoTokenizer.from_pretrained(str(tok_path), trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    return model, tokenizer


def extract_sql_from_text(raw: str) -> str:
    """Pull the first SELECT statement from model output."""
    text = str(raw).strip()
    upper = text.upper()
    if "SELECT" in upper:
        idx = upper.find("SELECT")
        sql = text[idx:].split(";")[0] + ";"
        return sql[:2000].strip()
    return text[:2000].strip()


def generate_optimized_sql(
    model: Any,
    tokenizer: Any,
    user_query: str,
    *,
    max_new_tokens: int = 512,
) -> str:
    """Run chat inference and return extracted SQL."""
    user_query = user_query.strip()
    messages = [
        {"role": "system", "content": SCHEMA_OPTIMIZATION_PROMPT},
        {
            "role": "user",
            "content": (
                f"Slow query:\n{user_query}\n\n"
                "Rewrite this slow query to be more efficient. Output ONLY the SQL, no explanation."
            ),
        },
    ]
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt, return_tensors="pt")
    dev = next(model.parameters()).device
    inputs = {k: v.to(dev) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
    return extract_sql_from_text(gen)
