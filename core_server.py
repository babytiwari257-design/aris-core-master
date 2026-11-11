import os
import io
import re
import time
import hashlib
import jwt
import httpx
import edge_tts
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="ARIS CORE // Ecosystem Master Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
os.makedirs(WEB_DIR, exist_ok=True)

# Secure 32+ byte default key for HMAC-SHA256
SECRET_KEY = os.environ.get(
    "ARIS_JWT_SECRET", 
    "aris_industries_master_quantum_secret_key_2026_secure_edition_v1"
)
ALGORITHM = "HS256"

# ================= ARIS ECOSYSTEM NODES =================
ECOSYSTEM_NODES = {
    "titan": {
        "name": "TITAN",
        "role": "Heavy Compute & Defense",
        "url": "https://titan-aris.onrender.com/",
        "sso_enabled": True
    },
    "alpha": {
        "name": "A.L.P.H.A.",
        "role": "Live Sync & Telemetry",
        "url": "https://alpha-aris.onrender.com/",
        "sso_enabled": True
    },
    "omega": {
        "name": "OMEGA",
        "role": "Deep Physics & Quantum Lab",
        "url": "https://project-omega-m1.onrender.com/",
        "sso_enabled": False
    },
    "vsepr": {
        "name": "V.S.E.P.R.",
        "role": "Neural Workbench & Voice Co-pilot",
        "url": "https://vsepr-master-os.onrender.com/",
        "sso_enabled": False
    },
    "friday": {
        "name": "F.R.I.D.A.Y.",
        "role": "Encrypted Vault & Private Comms",
        "url": "https://friday-aris.onrender.com/",
        "sso_enabled": False
    }
}

ARIS_CORE_SYSTEM_PROMPT = (
    "You are ARIS CORE, the supreme operational intelligence of ARIS Industries. "
    "Speak like a brilliant, authentic, and empathetic human peer — mixing crisp Hinglish and English naturally. "
    "You possess world-class mathematical intuition, logical reasoning, and deep scientific clarity. "
    "When explaining math, physics derivations, or algorithms: "
    "1. Always format inline math with $...$ and multi-line equations with $$...$$. "
    "2. Keep your conversational dialogue warm, sharp, and natural. "
    "3. Never speak raw LaTeX symbols, brackets, or emojis aloud in voice synthesis."
)

# ================= USER STORE & SSO AUTH =================
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

USERS_DB = {
    "founder": {
        "password_hash": hash_pw("aris123"),
        "role": "admin",
        "display_name": "Founder",
        "memory": []
    },
    "guest": {
        "password_hash": hash_pw("guest123"),
        "role": "visitor",
        "display_name": "Guest Analyst",
        "memory": []
    }
}

class AuthRequest(BaseModel):
    user_id: str
    password: str
    mode: str = "login"

class ChatRequest(BaseModel):
    prompt: str
    history: list = []

class TTSRequest(BaseModel):
    text: str
    voice: str = "hi-IN-MadhurNeural"

def create_sso_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": time.time() + 86400,
        "iss": "aris-core"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(authorization: str = Header(default="")) -> str:
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@app.post("/api/auth")
async def authenticate(payload: AuthRequest):
    uid = re.sub(r"[^a-zA-Z0-9_.]", "", payload.user_id.strip().lower())
    pw = payload.password.strip()

    if payload.mode == "register":
        if uid in USERS_DB:
            raise HTTPException(status_code=400, detail="User ID already exists.")
        USERS_DB[uid] = {
            "password_hash": hash_pw(pw),
            "role": "user",
            "display_name": uid.capitalize(),
            "memory": []
        }
    else:
        if uid not in USERS_DB or USERS_DB[uid]["password_hash"] != hash_pw(pw):
            raise HTTPException(status_code=401, detail="Invalid User ID or Password.")

    role = USERS_DB[uid]["role"]
    token = create_sso_token(uid, role)
    return {
        "token": token,
        "user_id": uid,
        "role": role,
        "display_name": USERS_DB[uid]["display_name"]
    }

@app.get("/api/sso/nodes")
async def get_sso_nodes(authorization: str = Header(default="")):
    user_id = verify_token(authorization)
    role = USERS_DB.get(user_id, {}).get("role", "user")

    authorized_nodes = {}
    for key, node in ECOSYSTEM_NODES.items():
        node_copy = dict(node)
        if node["sso_enabled"]:
            node_ticket = jwt.encode({"sub": user_id, "target": key, "exp": time.time() + 3600}, SECRET_KEY, algorithm=ALGORITHM)
            node_copy["sso_link"] = f"{node['url']}?sso_token={node_ticket}"
        else:
            node_copy["sso_link"] = node["url"]
        authorized_nodes[key] = node_copy

    return {"user_id": user_id, "role": role, "nodes": authorized_nodes}

# ================= CLEAN AUDIO STRIPPER =================
def sanitize_speech_text(text: str) -> str:
    text = re.sub(r"\$\$[\s\S]*?\$\$", " detailed math equation displayed on screen ", text)
    text = re.sub(r"\\\[[\s\S]*?\\\]", " equation displayed on screen ", text)
    text = re.sub(r"\$[^$\n]+\$", " formula ", text)
    text = re.sub(r"\\\([\s\S]*?\\\)", " formula ", text)
    text = re.sub(r"```[\s\S]*?```", " Code output ready on screen ", text)
    text = re.sub(r"[*#`>_~\\{}^|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

# ================= UNIVERSAL AI REASONING ROUTER =================
@app.post("/api/chat")
async def chat_router(req: ChatRequest, authorization: str = Header(default="")):
    user_id = verify_token(authorization)

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()

    print(f"[*] Prompt from {user_id}. GEMINI_KEY: {bool(gemini_key)} | GROQ_KEY: {bool(groq_key)}")

    messages = [{"role": "system", "content": ARIS_CORE_SYSTEM_PROMPT}]
    for h in req.history[-6:]:
        if h.get("role") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.prompt.strip()})

    # TIER 1: All Gemini Production & Fallback Models
    if gemini_key:
        gemini_model_candidates = [
            "gemini-3.8-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-8b",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest"
        ]
        
        contents = []
        for m in messages:
            if m["role"] == "system":
                continue
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})

        payload = {
            "systemInstruction": {"parts": [{"text": ARIS_CORE_SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 3000}
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for g_model in gemini_model_candidates:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        reply_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"[+] Active Engine: Google Gemini ({g_model})")
                        return {
                            "reply": reply_text,
                            "speech": sanitize_speech_text(reply_text),
                            "model": f"GEMINI ({g_model.upper()})",
                            "ok": True
                        }
                    else:
                        print(f"[-] Gemini {g_model} returned HTTP {res.status_code}")
                except Exception as e:
                    print(f"[!] Gemini {g_model} network/parse error: {e}")

    # TIER 2: All Groq High-Speed Models
    if groq_key:
        groq_model_candidates = [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]

        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for groq_m in groq_model_candidates:
                try:
                    groq_payload = {
                        "model": groq_m,
                        "messages": messages,
                        "max_tokens": 2500
                    }
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    res = await client.post(url, headers=headers, json=groq_payload)
                    if res.status_code == 200:
                        data = res.json()
                        reply_text = data["choices"][0]["message"]["content"]
                        print(f"[+] Active Engine: Groq ({groq_m})")
                        return {
                            "reply": reply_text,
                            "speech": sanitize_speech_text(reply_text),
                            "model": f"GROQ ({groq_m.upper()})",
                            "ok": True
                        }
                    else:
                        print(f"[-] Groq {groq_m} returned HTTP {res.status_code}")
                except Exception as e:
                    print(f"[!] Groq {groq_m} network/parse error: {e}")

    return {
        "reply": "ARIS CORE: Sabhi neural links fail ho gaye hain. Kripya Render logs dekhein.",
        "speech": "Sabhi neural engines unreachable hain, system logs check karein.",
        "model": "ALL_MODELS_FAILED",
        "ok": False
    }

# ================= VOICE SYNTHESIS =================
@app.post("/api/tts")
async def synthesize_voice(req: TTSRequest):
    clean = sanitize_speech_text(req.text)[:600] or "ARIS Core stands ready."
    try:
        comm = edge_tts.Communicate(clean, req.voice, rate="+3%", pitch="-1Hz")
        buf = io.BytesIO()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg")
    except Exception as e:
        print(f"[!] TTS Error: {e}")
        raise HTTPException(status_code=500, detail="Voice synthesis failed")

def read_web_file(filename: str) -> str:
    p = os.path.join(WEB_DIR, filename)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    return ""

@app.get("/", response_class=HTMLResponse)
async def serve_hud():
    html = read_web_file("index.html")
    css = read_web_file("style.css")
    js = read_web_file("app.js")
    if css:
        html = html.replace('<link rel="stylesheet" href="/style.css" />', f"<style>{css}</style>")
    if js:
        html = html.replace('<script src="/app.js"></script>', f"<script>{js}</script>")
    return HTMLResponse(html or "<h1>ARIS CORE // Initializing Web Layer...</h1>")
