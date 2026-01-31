# AURORA Local Agent MVP (Offline-first, user-provided API key)

Minimal local-only desktop app skeleton:
- Electron desktop shell + simple Web UI
- FastAPI local backend (127.0.0.1) hosting the Agent core
- SQLite memory store (semantic + episodic + conversation summaries)
- Context Assembler with a hard budget (token approx by chars)

No servers. Everything stays on the user's machine.
User supplies their own LLM API key + endpoint in Settings.

## Quick start (Dev)

### 1) Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell
pip install -r requirements.txt
python main.py
```
Backend runs on http://127.0.0.1:8787

### 2) Desktop App
```bash
cd app
npm install
npm run dev
```

## Packaging (Optional)
```bash
cd app
npm run dist
```
Outputs go to `app/dist/`.

## Notes
- Token budgeting is approximated by characters in this MVP. Swap in a real tokenizer later.
- Embeddings are stubbed (simple keyword scoring). Add embedding calls when you choose an embedding model.
- API keys are stored in a local JSON file in this MVP. For production, store in OS keychain (e.g., keytar).
