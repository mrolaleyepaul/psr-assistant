"""Step 4: API. Run with: uvicorn main:app --reload"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag import answer

app = FastAPI(title="PSR Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Turn(BaseModel):
    role: str  # "user" or "model"
    text: str

class Ask(BaseModel):
    question: str
    history: list[Turn] = []
    audience: str = "standard"  # simple | standard | detailed

@app.post("/ask")
def ask(body: Ask):
    return answer(body.question, [t.model_dump() for t in body.history], body.audience)

@app.get("/")
def home():
    return {"service": "PSR Assistant", "ask": "POST /ask", "docs": "/docs"}

@app.get("/health")
def health():
    return {"ok": True}
