import hashlib
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from google import genai

ROOT=Path(__file__).resolve().parents[1]
STATE_FILE=ROOT/"data/state.json"
PRIORITY_FILE=ROOT/"priority.txt"
DEFAULT_HASHTAGS="#HindiQuotes #LifeQuotes #Zindagi #Motivation #PositiveVibes"

def clean(v): return " ".join(v.replace("\r"," ").replace("\n"," ").split()).strip()
def norm(v): return re.sub(r"[^\w\u0900-\u097F]+","",clean(v).lower())
def h(v): return hashlib.sha256(norm(v).encode("utf-8")).hexdigest()

def get_priority_quote():
    if not PRIORITY_FILE.exists(): return None,None
    for n,line in enumerate(PRIORITY_FILE.read_text(encoding="utf-8").splitlines(),1):
        text=clean(line)
        if text and not text.startswith("#"): return text,n
    return None,None

def remove_priority_quote(line_number):
    if not line_number or not PRIORITY_FILE.exists(): return
    lines=PRIORITY_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    i=line_number-1
    if 0<=i<len(lines):
        del lines[i]
        PRIORITY_FILE.write_text("".join(lines),encoding="utf-8")

def state():
    return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
def save(s):
    STATE_FILE.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding="utf-8")
def client():
    key=os.getenv("GEMINI_API_KEY","").strip()
    if not key: raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=key)
def model():
    m=os.getenv("GEMINI_MODEL","").strip()
    if not m: raise RuntimeError("GEMINI_MODEL is not configured.")
    return m

def too_similar(q,recent):
    nq=norm(q)
    return any(SequenceMatcher(None,nq,norm(x)).ratio()>=0.90 for x in recent[-100:] if norm(x))

def generate_gemini_quote():
    s=state(); recent=s.get("recent_gemini_quotes",[]); used=set(s.get("used_gemini_quote_hashes",[]))
    recent_text="\n".join(f"- {q}" for q in recent[-50:]) or "(none)"
    prompt=f"""Generate exactly ONE original Hindi life quote for a daily Instagram diary page.
Rules:
- only the quote
- Hindi/Devanagari
- 8 to 22 Hindi words
- emotional, natural, relatable, meaningful
- no hashtags, emojis, quotes, attribution, numbering or explanation
- do not repeat or closely paraphrase these recent quotes:
{recent_text}"""
    last=None
    for _ in range(5):
        try:
            r=client().models.generate_content(model=model(),contents=prompt)
            q=clean(r.text or "")
            if not q or len(q.split())<4: raise ValueError("empty/short quote")
            if any(x in q for x in ["#","http://","https://"]): raise ValueError("invalid quote")
            if h(q) in used or too_similar(q,recent): raise ValueError("duplicate or too similar")
            recent.append(q); used.add(h(q))
            s["recent_gemini_quotes"]=recent[-100:]; s["used_gemini_quote_hashes"]=list(used)[-10000:]
            save(s); return q
        except Exception as e:
            last=e
            print("Quote rejected:",e)
    raise RuntimeError(f"Could not generate unique quote: {last}")

def tags(text):
    return list(dict.fromkeys(re.findall(r"#[\w\u0900-\u097F]+",text)))[:5]
def generate_hashtags(quote):
    try:
        r=client().models.generate_content(model=model(),contents=f"""Return exactly 5 relevant Instagram hashtags for this Hindi life quote.
Quote: {quote}
Rules: hashtags only, separated by spaces; mostly English; no explanation.""")
        t=tags(r.text or "")
        if len(t)>=5: return " ".join(t[:5])
    except Exception as e: print("Hashtag generation failed:",e)
    return os.getenv("HASHTAGS",DEFAULT_HASHTAGS)

def get_quote():
    force=os.getenv("FORCE_GEMINI","false").lower()=="true"
    if not force:
        q,line=get_priority_quote()
        if q: return q,"priority",line
    return generate_gemini_quote(),"gemini",None
