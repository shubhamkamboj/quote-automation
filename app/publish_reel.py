import json,os,sys,time,requests
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; META=ROOT/"generated/latest.json"; TOKEN=os.getenv("INSTAGRAM_ACCESS_TOKEN","").strip(); USER=os.getenv("INSTAGRAM_ACCOUNT_ID","").strip(); VER=os.getenv("META_API_VERSION","").strip() or "v25.0"; REEL=os.getenv("REEL_URL","").strip()
def u(p): return f"https://graph.instagram.com/{VER}/{p}"
def post(p,d):
 r=requests.post(u(p),data=d,timeout=120)
 if not r.ok: raise RuntimeError(f"Instagram API error {r.status_code}: {r.text}")
 return r.json()
def get(p,d):
 r=requests.get(u(p),params=d,timeout=90)
 if not r.ok: raise RuntimeError(f"Instagram API error {r.status_code}: {r.text}")
 return r.json()
def main():
 if not TOKEN or not USER or not REEL: raise RuntimeError("INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID and REEL_URL are required.")
 m=json.loads(META.read_text(encoding="utf-8")); cap=f'{m["quote"]}\n\n{m.get("hashtags","")}'.strip()
 r=requests.get(REEL,stream=True,allow_redirects=True,timeout=45); ct=(r.headers.get("Content-Type") or "").lower()
 if not r.ok or not ct.startswith("video/mp4"): raise RuntimeError(f"Reel URL invalid: HTTP {r.status_code}, {ct}")
 c=post(f"{USER}/media",{"media_type":"REELS","video_url":REEL,"caption":cap,"share_to_feed":"true","access_token":TOKEN}); cid=c.get("id")
 if not cid: raise RuntimeError(f"No reel container: {c}")
 for i in range(30):
  s=get(cid,{"fields":"status_code,status","access_token":TOKEN}); code=s.get("status_code"); print("Reel",i+1,code)
  if code=="FINISHED": break
  if code in {"ERROR","EXPIRED"}: raise RuntimeError(str(s))
  time.sleep(10)
 else: raise RuntimeError("Reel container timeout")
 p=post(f"{USER}/media_publish",{"creation_id":cid,"access_token":TOKEN})
 if not p.get("id"): raise RuntimeError(f"No reel media id: {p}")
 print("REEL:",p["id"])
if __name__=="__main__":
 try: main()
 except Exception as e: print("ERROR:",e,file=sys.stderr); sys.exit(1)
