"""GRPO Training for Autonomic DBRE — Schema-aware prompts."""

import os, json, time, torch

os.environ["DB_USER"] = os.getenv("DB_USER", "dbre_admin")
os.environ["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "dbre_pass")

from dbre.environment import DBREEnvironment, DBREAction
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model
from trl import GRPOConfig, GRPOTrainer
from datasets import Dataset

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

# Load model
print("Loading Qwen2.5-Coder-1.5B...")
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-Coder-1.5B-Instruct", quantization_config=bnb, device_map="auto", trust_remote_code=True)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-1.5B-Instruct", trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
model = get_peft_model(model, LoraConfig(r=16, lora_alpha=16, lora_dropout=0, target_modules=["q_proj","k_proj","v_proj","o_proj"], bias="none", task_type="CAUSAL_LM"))
print("Model loaded.")

# Reward
def dbre_reward(completions, **kwargs):
    env = DBREEnvironment({'max_steps': 5})
    rewards = []
    for c in completions:
        obs = env.reset()
        try:
            raw = str(c).strip()
            # Extract SQL: find SELECT and take everything after it
            if "SELECT" in raw.upper():
                idx = raw.upper().find("SELECT")
                sql = raw[idx:].split(";")[0] + ";"
                sql = sql[:500]
            else:
                sql = raw[:500]
            a = DBREAction(action_type="rewrite_query", new_sql=sql)
            _, r, _, info = env.step(a)
            rb = info.get('reward_breakdown', {})
            score = rb.get('efficiency', 0) * 0.5 + rb.get('correctness', 0) * 0.3 + rb.get('style', 0) * 0.2
            scaled = min(1.0, max(0.0, score * 2.0 - 0.2))
            rewards.append(float(scaled))
        except Exception as e:
            rewards.append(0.0)
    return rewards

# Dataset with schema-aware prompts
dummy = Dataset.from_dict({"prompt": [SCHEMA_PROMPT] * 100})

# Train
trainer = GRPOTrainer(
    model=model, processing_class=tokenizer,
    args=GRPOConfig(output_dir="./grpo_dbre", num_train_epochs=1, per_device_train_batch_size=2,
                    gradient_accumulation_steps=8, learning_rate=5e-5, logging_steps=5,
                    save_steps=50, max_steps=500, bf16=True, report_to="none"),
    train_dataset=dummy, reward_funcs=[dbre_reward],
)

print("Training with schema-aware prompts...")
trainer.train()

model.save_pretrained("./dbre_trained")
tokenizer.save_pretrained("./dbre_trained")
print("Done. Model saved to ./dbre_trained")
