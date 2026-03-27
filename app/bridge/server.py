from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import os

app = FastAPI()
TOKEN = os.getenv("BRIDGE_TOKEN", "")
state = {"snapshot": None, "last_error": None, "pending_command": None, "last_result": None}


def auth(authorization: Optional[str]):
    if not TOKEN:
        raise HTTPException(500, "bridge token missing")
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")


class AnyPayload(BaseModel):
    __root__: Any


@app.post("/bridge/snapshot")
def bridge_snapshot(payload: dict, authorization: Optional[str] = Header(None)):
    auth(authorization)
    state["snapshot"] = payload
    return {"ok": True}


@app.get("/bridge/command")
def bridge_command(authorization: Optional[str] = Header(None)):
    auth(authorization)
    cmd = state["pending_command"]
    state["pending_command"] = None
    return cmd or {"command": None}


@app.post("/bridge/result")
def bridge_result(payload: dict, authorization: Optional[str] = Header(None)):
    auth(authorization)
    state["last_result"] = payload
    return {"ok": True}


@app.post("/bridge/error")
def bridge_error(payload: dict, authorization: Optional[str] = Header(None)):
    auth(authorization)
    state["last_error"] = payload
    return {"ok": True}


@app.get("/bridge/state")
def bridge_state(authorization: Optional[str] = Header(None)):
    auth(authorization)
    return state


@app.post("/bridge/command/close_all")
def bridge_command_close_all(authorization: Optional[str] = Header(None)):
    auth(authorization)
    state["pending_command"] = {"command": "close_all"}
    return {"ok": True}
