# PSR Assistant

Explains the Nigerian Public Service Rules (2021 Edition) to government workers, citing rule numbers.

## Setup
    python -m venv venv && venv\Scripts\activate      # Windows
    pip install -r requirements.txt
    copy .env.example .env                           # then add your Gemini key

## Run
    python ingest.py          # once: embeds ~500 rules into data/chroma
    python rag.py             # quick test from the terminal
    uvicorn main:app --reload # API at http://127.0.0.1:8000/docs

`data/psr_rules.json` is already parsed. Re-run `parse_psr.py` only if you change the source document.

## Example request
    POST /ask
    {"question": "Can I take casual leave and annual leave together?", "history": []}
