"""GRPO Training for Autonomic DBRE using Qwen2.5-Coder-1.5B + Unsloth."""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any

import torch
from dbre.environment import DBREEnvironment, DBREAction, DBREObservation


# ============================================================
# CONFIG
# ============================================================
MODEL_NAME = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
MAX_EPISODES = 500
MAX_STEPS_PER_EPISODE = 10
SAVE_EVERY = 100
LEARNING_RATE = 5e-5
OUTPUT_DIR = "./trained_model"


# ============================================================
# SIMPLE POLICY (no GRPO yet — just random agent as baseline)
# Replace this with GRPOTrainer after verifying env works
# ============================================================
class SimplePolicy:
    """Random agent that picks actions. Replace with GRPO-trained model."""
    
    REWRITE_TEMPLATES = [
        "SELECT c.name, o.order_date FROM customers c JOIN orders o ON c.customer_id = o.customer_id WHERE o.status = 'pending' LIMIT 20",
        "SELECT p.name, SUM(oi.quantity) as total_sold FROM products p JOIN order_items oi ON p.product_id = oi.product_id GROUP BY p.name ORDER BY total_sold DESC LIMIT 10",
        "SELECT c.name, COUNT(o.order_id) as order_count FROM customers c JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.name HAVING COUNT(o.order_id) > 2",
        "SELECT p.category, AVG(r.rating) as avg_rating FROM products p JOIN reviews r ON p.product_id = r.product_id GROUP BY p.category",
        "SELECT o.order_id, c.name, o.order_date FROM orders o JOIN customers c ON o.customer_id = c.customer_id WHERE o.order_date > NOW() - INTERVAL '30 days'",
    ]
    
    def select_action(self, observation: DBREObservation) -> DBREAction:
        import random
        return DBREAction(
            action_type="rewrite_query",
            new_sql=random.choice(self.REWRITE_TEMPLATES)
        )


# ============================================================
# TRAINING LOOP
# ============================================================
def train():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting training...")
    print(f"Model: {MODEL_NAME}")
    print(f"Max episodes: {MAX_EPISODES}")
    print(f"Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
    print()
    
    env = DBREEnvironment({'max_steps': MAX_STEPS_PER_EPISODE, 'latency_threshold_pct': 0.6})
    policy = SimplePolicy()
    
    episode_rewards = []
    best_reward = -999
    reward_history = []
    
    for episode in range(1, MAX_EPISODES + 1):
        obs = env.reset()
        episode_reward = 0
        steps_taken = 0
        
        for step in range(MAX_STEPS_PER_EPISODE):
            action = policy.select_action(obs)
            obs, reward, done, info = env.step(action)
            episode_reward += reward
            steps_taken += 1
            if done:
                break
        
        episode_rewards.append(episode_reward)
        
        # Running average
        if len(episode_rewards) >= 10:
            avg_reward = sum(episode_rewards[-10:]) / 10
        else:
            avg_reward = sum(episode_rewards) / len(episode_rewards)
        
        reward_history.append({
            "episode": episode,
            "reward": round(episode_reward, 4),
            "avg_reward_10": round(avg_reward, 4),
            "steps": steps_taken,
            "timestamp": time.time()
        })
        
        if episode_reward > best_reward:
            best_reward = episode_reward
        
        if episode % 10 == 0:
            elo_data = env.elo_tracker.get_elo_curve_data()
            champion = env.elo_tracker.get_current_champion()
            print(f"[Ep {episode:4d}] reward={episode_reward:.3f} avg10={avg_reward:.3f} "
                  f"best={best_reward:.3f} steps={steps_taken} champion={champion}")
        
        # Save checkpoint
        if episode % SAVE_EVERY == 0:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            checkpoint = {
                "episode": episode,
                "reward_history": reward_history,
                "elo_history": env.elo_tracker.history,
                "champion": env.elo_tracker.get_current_champion(),
                "playbook": env.playbook_manager.get_current()
            }
            with open(f"{OUTPUT_DIR}/checkpoint_ep{episode}.json", "w") as f:
                json.dump(checkpoint, f, indent=2, default=str)
            print(f"  → Saved checkpoint at episode {episode}")
    
    # Final save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(f"{OUTPUT_DIR}/final_results.json", "w") as f:
        json.dump({
            "total_episodes": MAX_EPISODES,
            "best_reward": best_reward,
            "final_avg_reward": sum(episode_rewards[-50:]) / 50 if len(episode_rewards) >= 50 else sum(episode_rewards) / len(episode_rewards),
            "reward_history": reward_history,
            "elo_history": env.elo_tracker.history,
            "final_playbook": env.playbook_manager.get_current(),
            "champion": env.elo_tracker.get_current_champion()
        }, f, indent=2, default=str)
    
    print(f"\n[✓] Training complete!")
    print(f"Best reward: {best_reward:.3f}")
    print(f"Champion playbook: {env.elo_tracker.get_current_champion()}")
    print(f"Results saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    train()
