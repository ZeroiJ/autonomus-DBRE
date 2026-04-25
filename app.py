from __future__ import annotations

import requests
import plotly.graph_objects as go

API_BASE = "http://localhost:8000"


def api_get(endpoint: str):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=5)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def api_post(endpoint: str, data: dict):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=5)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def inject_chaos():
    data = api_post("/reset", {})
    obs = data.get("observation", {})
    return (
        obs.get("broken_query", ""),
        obs.get("baseline_latency_ms", 0),
        obs.get("schema_description", ""),
        str(obs.get("schema_diff", [])),
        obs.get("agent_playbook", ""),
        get_elo_chart(),
        "---",
        0.0, 0.0, 0.0, 0.0, 0.0,
        "Waiting for agent action...",
        0.0, "---"
    )


def agent_step(action_type, sql_text, index_table, index_col):
    payload = {
        "action_type": action_type,
        "new_sql": sql_text if action_type == "rewrite_query" else None,
        "table_name": index_table if action_type == "add_index" else None,
        "column_name": index_col if action_type == "add_index" else None,
        "diff": None
    }
    data = api_post("/step", payload)
    obs = data.get("observation", {})
    info = data.get("info", {})
    rb = info.get("reward_breakdown", {})
    reward = data.get("reward", 0)
    done = data.get("terminated", False)

    status = f"Step {obs.get('attempts', 0)} | Reward: {reward:.3f} | {'DONE' if done else 'ACTIVE'}"
    return (
        rb.get("correctness", 0),
        rb.get("efficiency", 0),
        rb.get("style", 0),
        rb.get("anticheat", 0),
        rb.get("total", 0),
        f"{obs.get('current_score', 0):.3f}",
        obs.get("agent_playbook", ""),
        status,
        get_elo_chart()
    )


def get_elo_chart():
    data = api_get("/elo_history")
    history = data.get("history", [])
    if not history:
        fig = go.Figure()
        fig.add_annotation(text="No ELO data yet", x=0.5, y=0.5, showarrow=False,
                          font=dict(color="white", size=16))
        fig.update_layout(paper_bgcolor="#1a1a2e", plot_bgcolor="#1a1a2e")
        return fig

    versions = [h.get("version", f"v{i}") for i, h in enumerate(history)]
    elos = [h.get("elo", 1000) for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(elos))),
        y=elos,
        mode="lines+markers",
        line=dict(color="#00ff88", width=3),
        marker=dict(size=10, color="#00ff88"),
        text=versions,
        hovertemplate="%{text}<br>ELO: %{y:.0f}<extra></extra>"
    ))
    fig.update_layout(
        title=dict(text="🧬 Playbook ELO Evolution", font=dict(color="white", size=18)),
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        font=dict(color="white"),
        xaxis=dict(title="Version", gridcolor="#333", tickfont=dict(color="white")),
        yaxis=dict(title="ELO Rating", gridcolor="#333", tickfont=dict(color="white")),
        margin=dict(l=40, r=20, t=50, b=40),
        height=350
    )
    return fig


def reward_bar_html(c, e, s, a):
    def bar(name, val):
        color = "#00ff88" if val > 0.7 else ("#ffcc00" if val > 0.4 else "#ff4444")
        w = max(int(val * 100), 2)
        return f"""
        <div style="margin-bottom:6px">
            <div style="display:flex;justify-content:space-between;color:white;font-size:11px">
                <span>{name}</span><span>{val:.3f}</span>
            </div>
            <div style="background:#333;height:18px;border-radius:4px;overflow:hidden">
                <div style="background:{color};width:{w}%;height:100%;transition:width 0.3s"></div>
            </div>
        </div>"""
    return f"<div style='background:#1a1a2e;padding:12px;border-radius:8px'>{bar('Correctness',c)}{bar('Efficiency',e)}{bar('Style',s)}{bar('Anticheat',a)}</div>"


CSS = """
body { background: #0d0d1a; }
.gradio-container { background: #0d0d1a; max-width: 1200px !important; }
.gr-button-primary { background: #00ff88 !important; color: #000 !important; font-weight: bold !important; }
.gr-button-secondary { background: #333 !important; color: #fff !important; }
.gr-textbox textarea { background: #1a1a2e !important; color: #fff !important; border: 1px solid #333 !important; }
label { color: #aaa !important; }
"""

with __import__("gradio").Blocks(css=CSS, title="Autonomic DBRE") as demo:
    __import__("gradio").Markdown("# 🧠 Autonomic DBRE — Self-Improving Database Agent")

    with __import__("gradio").Row():
        with __import__("gradio").Column(scale=1):
            __import__("gradio").Markdown("### 💥 Inject Chaos")
            chaos_btn = __import__("gradio").Button("Inject Database Chaos", variant="primary")
            broken_q = __import__("gradio").Textbox(label="Broken Query", lines=6, interactive=False)
            baseline_l = __import__("gradio").Textbox(label="Baseline Latency (ms)", interactive=False)
            schema_info = __import__("gradio").Textbox(label="Schema", interactive=False)
            schema_diff = __import__("gradio").Textbox(label="Schema Drift", interactive=False)
            playbook_display = __import__("gradio").Textbox(label="Current Playbook", lines=8, interactive=False)

        with __import__("gradio").Column(scale=1):
            __import__("gradio").Markdown("### 🤖 Agent Controls")
            action_dd = __import__("gradio").Dropdown(
                choices=["rewrite_query", "add_index", "commit_playbook_diff"],
                label="Action Type", value="rewrite_query"
            )
            sql_input = __import__("gradio").Textbox(label="SQL (for rewrite)", lines=4, placeholder="SELECT ...")
            idx_table = __import__("gradio").Textbox(label="Table (for add_index)")
            idx_col = __import__("gradio").Textbox(label="Column (for add_index)")
            step_btn = __import__("gradio").Button("Execute Step", variant="secondary")
            status_out = __import__("gradio").Textbox(label="Status", interactive=False)

    __import__("gradio").Markdown("### 📊 Rewards")
    reward_html = __import__("gradio").HTML(value=reward_bar_html(0, 0, 0, 0))
    with __import__("gradio").Row():
        c_out = __import__("gradio").Textbox(label="Correctness", interactive=False)
        e_out = __import__("gradio").Textbox(label="Efficiency", interactive=False)
        s_out = __import__("gradio").Textbox(label="Style", interactive=False)
        a_out = __import__("gradio").Textbox(label="Anticheat", interactive=False)
        t_out = __import__("gradio").Textbox(label="Total", interactive=False)

    __import__("gradio").Markdown("### 📈 ELO Evolution")
    elo_chart = __import__("gradio").Plot(value=get_elo_chart(), label="ELO Over Time")

    chaos_btn.click(
        inject_chaos,
        outputs=[broken_q, baseline_l, schema_info, schema_diff, playbook_display,
                 elo_chart, status_out, c_out, e_out, s_out, a_out, t_out, sql_input, baseline_l, status_out]
    )

    step_btn.click(
        agent_step,
        inputs=[action_dd, sql_input, idx_table, idx_col],
        outputs=[c_out, e_out, s_out, a_out, t_out, baseline_l, playbook_display, status_out, elo_chart]
    )

    step_btn.click(lambda c, e, s, a: reward_bar_html(c, e, s, a),
                   inputs=[c_out, e_out, s_out, a_out], outputs=[reward_html])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
