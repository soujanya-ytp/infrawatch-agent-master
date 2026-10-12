# Setup Guide — {{AGENT_NAME}}

## Prerequisites

- Python 3.10+
- A Groq API key (free tier): https://console.groq.com

---

## Step-by-Step

```bash
# 1. Clone / navigate to project
cd ~/agent-{{domain}}

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and set:
#   GROQ_API_KEY=<your key from console.groq.com>
#   GROQ_MODEL=llama3-8b-8192   (default, change if needed)

# 5. Verify setup
python -c "from src.state import AgentState; print('OK')"

# 6. Run tests (should all pass — no GROQ_API_KEY needed)
pytest tests/ -v

# 7. Run automated demo
python src/agent.py --demo

# 8. Or run interactive CLI
python src/agent.py
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| GROQ_API_KEY | YES (for live) | "" | Groq API key |
| GROQ_MODEL | no | llama3-8b-8192 | Model name |
| MAX_RETRIES | no | 3 | Max retry attempts |
| MAX_ITERATIONS | no | 8 | Max agent loop iterations |
| MAX_EXECUTION_TIME | no | 120 | Seconds before timeout |

---

## Troubleshooting

**Tests fail with `NotImplementedError`**
→ Tool stubs not yet implemented. Fill in `TODO` blocks in each tool file.

**`GROQ_API_KEY not set` warning**
→ Tests pass without it. Only needed for live `--demo` or `run_cli()`.

**`pd.read_csv` returns "nan" for empty fields**
→ Always use `keep_default_na=False` parameter.

**`pytest` not found**
→ Activate venv: `source venv/bin/activate`

**`ModuleNotFoundError: src`**
→ Run from project root: `cd ~/agent-{{domain}} && pytest tests/ -v`
   Or set: `PYTHONPATH=. pytest tests/ -v`
