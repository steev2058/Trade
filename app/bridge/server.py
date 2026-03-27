from fastapi import FastAPI, Header, HTTPException
from typing import Optional
import os

app = FastAPI()
TOKEN = os.getenv("BRIDGE_TOKEN", "")
state = {"snapshot": None, "last_error": None, "pending_command": None, "last_result": None}


def auth(authorization: Optional[str]):
    if not TOKEN:
        raise HTTPException(500, "bridge token missing")
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")


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
def bridge_command_close_all(payload: dict | None = None, authorization: Optional[str] = Header(None)):
    auth(authorization)
    payload = payload or {}
    state["pending_command"] = {"command": "close_all", "cmd_id": payload.get("cmd_id")}
    return {"ok": True}


@app.post("/bridge/command/open")
def bridge_command_open(payload: dict, authorization: Optional[str] = Header(None)):
    auth(authorization)
    state["pending_command"] = {
        "command": "open",
        "symbol": payload.get("symbol"),
        "side": payload.get("side"),
        "lot": payload.get("lot"),
        "cmd_id": payload.get("cmd_id"),
    }
    return {"ok": True}


@app.post("/bridge/command/close")
def bridge_command_close(payload: dict, authorization: Optional[str] = Header(None)):
    auth(authorization)
    state["pending_command"] = {
        "command": "close",
        "ticket": payload.get("ticket"),
        "cmd_id": payload.get("cmd_id"),
    }
    return {"ok": True}


@app.post("/bridge/command/sl_tp")
def bridge_command_sl_tp(payload: dict, authorization: Optional[str] = Header(None)):
    auth(authorization)
    state["pending_command"] = {
        "command": "sl_tp",
        "ticket": payload.get("ticket"),
        "sl": payload.get("sl"),
        "tp": payload.get("tp"),
        "cmd_id": payload.get("cmd_id"),
    }
    return {"ok": True}
