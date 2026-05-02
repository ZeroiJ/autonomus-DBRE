"""GRPO Training for Autonomic DBRE — Schema-aware prompts."""

from __future__ import annotations

import os

os.environ.setdefault("DB_USER", os.getenv("DB_USER", "dbre_admin"))
os.environ.setdefault("DB_PASSWORD", os.getenv("DB_PASSWORD", "dbre_pass"))
os.environ.setdefault("DB_HOST", os.getenv("DB_HOST", "localhost"))
os.environ.setdefault("DB_PORT", os.getenv("DB_PORT", "5432"))
os.environ.setdefault("DB_NAME", os.getenv("DB_NAME", "dbre"))

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import GRPOConfig, GRPOTrainer

from dbre.environment import DBREAction, DBREEnvironment
from dbre.rewards import weighted_total_from_breakdown

SCHEMA_PROMPT = """You are a SQL optimization expert. Given a slow query, rewrite it to be faster.

Database schema:
- customers(customer_id, name, email, city, created_at)
- products(product_id, name, category, price, stock)
- orders(order_id, customer_id, order_date, status)
- order_items(item_id, order_id, product_id, quantity, unit_price)
- reviews(review_id, customer_id, product_id, rating, review_text, created_at)

Rules:
- Use only the tables and columns above
- Add JOINs with proper ON conditions
- No SELECT *
- Use specific column names
- Add WHERE clauses to filter rows
- Use LIMIT for large result sets
- Use indexes: customers(email), orders(customer_id), order_items(order_id), reviews(customer_id)

Rewrite this slow query to be more efficient. Output ONLY the SQL, no explanation."""

# Populated during training for plotting (mean reward per reward batch)
REWARD_HISTORY: list[float] = []


def dbre_reward(completions, **kwargs):
    env = DBREEnvironment({"max_steps": 5})
    rewards = []
    for c in completions:
        try:
            env.reset()
            raw = str(c).strip()
            if "SELECT" in raw.upper():
                idx = raw.upper().find("SELECT")
                sql = raw[idx:].split(";")[0] + ";"
                sql = sql[:500]
            else:
                sql = raw[:500]
            a = DBREAction(action_type="rewrite_query", new_sql=sql)
            _, _r, _, info = env.step(a)
            rb = info.get("reward_breakdown", {})
            # Row-count correctness + fixed weights (see ``dbre.rewards``)
            total = weighted_total_from_breakdown(rb)
            rewards.append(total)
        except Exception:
            rewards.append(0.0)
    if rewards:
        REWARD_HISTORY.append(sum(rewards) / len(rewards))
    return rewards


def run_training(
    output_dir: str = "./grpo_dbre",
    save_dir: str = "./dbre_trained",
    max_steps: int = 300,
    save_steps: int = 50,
) -> list[float]:
    """Run GRPO with Qwen2.5-Coder-1.5B, 4-bit QLoRA; save adapter + tokenizer to ``save_dir``."""
    global REWARD_HISTORY
    REWARD_HISTORY.clear()

    print("Loading Qwen2.5-Coder-1.5B...")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen2.5-Coder-1.5B-Instruct",
        quantization_config=bnb,
        device_map="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        "Qwen/Qwen2.5-Coder-1.5B-Instruct", trust_remote_code=True
    )
    tokenizer.pad_token = tokenizer.eos_token
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=16,
            lora_dropout=0,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            bias="none",
            task_type="CAUSAL_LM",
        ),
    )
    print("Model loaded.")

    dummy = Dataset.from_dict({"prompt": [SCHEMA_PROMPT] * 100})

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        args=GRPOConfig(
            output_dir=output_dir,
            num_train_epochs=1,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            learning_rate=5e-5,
            logging_steps=5,
            save_steps=save_steps,
            max_steps=max_steps,
            bf16=True,
            report_to="none",
        ),
        train_dataset=dummy,
        reward_funcs=[dbre_reward],
    )

    print("Training with schema-aware prompts...")
    trainer.train()

    os.makedirs(save_dir, exist_ok=True)
    model.save_pretrained(save_dir)
    tokenizer.save_pretrained(save_dir)
    print(f"Done. Model saved to {save_dir}")

    return list(REWARD_HISTORY)


if __name__ == "__main__":
    run_training()
