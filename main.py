"""
main.py — API de matching de produtos por texto normalizado.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from matcher import match_lista
from stage1_rules import classificar

app = FastAPI(title="Matcher API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MatchRequest(BaseModel):
    itens: list[str]
    catalogo: list[dict]
    threshold: int = 60


@app.post("/match")
def match(body: MatchRequest):
    resultados = match_lista(body.itens, body.catalogo, body.threshold)
    return {"itens": resultados}


class Stage1Request(BaseModel):
    mensagem: str


@app.post("/stage1")
def stage1(body: Stage1Request):
    return classificar(body.mensagem)


@app.get("/health")
def health():
    return {"ok": True}
