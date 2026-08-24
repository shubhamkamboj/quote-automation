import json, random
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
TEMPLATES=ROOT/"templates"; OUT=ROOT/"generated"; STATE=ROOT/"data/state.json"; FONT=ROOT/"fonts/NotoSansDevanagari-Regular.ttf"
W,H=1080,1800
def load(p,d):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
def pick():
    from quote_source import get_quote
    q,src,line=get_quote()
    templates=sorted(TEMPLATES.glob("template-*.jpg"))
    if not templates: raise RuntimeError("No templates found.")
    s=load(STATE,{"last_template":None})
    c=[p for p in templates if p.name!=s.get("last_template")] or templates
    t=random.SystemRandom().choice(c)
    s.update(last_template=t.name,last_quote_source=src,last_run_utc=datetime.now(timezone.utc).isoformat()); save(STATE,s)
    return q,t,src,line
def font(n): return ImageFont.truetype(str(FONT),n)
def wrap(d,text,f,maxw):
    out=[]; cur=""
    for word in text.split():
        c=word if not cur else cur+" "+word
        if d.textbbox((0,0),c,font=f)[2]<=maxw: cur=c
        else:
            if cur: out.append(cur)
            cur=word
    if cur: out.append(cur)
    return "\n".join(out)
def fit(d,q,maxw,maxh):
    for n in range(58,27,-2):
        f=font(n); w=wrap(d,q,f,maxw); b=d.multiline_textbbox((0,0),w,font=f,spacing=18,align="center")
        if b[2]-b[0]<=maxw and b[3]-b[1]<=maxh: return w,f
    f=font(28); return wrap(d,q,f,maxw),f
def render(q,tp):
    im=Image.open(tp).convert("RGB").resize((W,H),Image.Resampling.LANCZOS); d=ImageDraw.Draw(im,"RGBA")
    l,r,t,b=115,965,170,1690; text,f=fit(d,q,r-l-80,b-t-80); cx=(l+r)//2; cy=(t+b)//2
    bb=d.multiline_textbbox((0,0),text,font=f,spacing=18,align="center"); th=bb[3]-bb[1]
    d.multiline_text((cx,cy),text,font=f,anchor="mm",align="center",spacing=18,fill=(72,55,42,255))
    y=cy+th//2+48
    if y<b-25:
        d.line((cx-106,y,cx-26,y),fill=(150,116,79,180),width=2); d.text((cx,y),"♥",font=font(24),anchor="mm",fill=(150,116,79,210)); d.line((cx+26,y,cx+106,y),fill=(150,116,79,180),width=2)
    return im
def main():
    q,t,src,line=pick(); im=render(q,t); now=datetime.now(timezone.utc); fn=f"quote-{now.strftime('%Y%m%d-%H%M%S-%f')}.jpg"
    OUT.mkdir(parents=True,exist_ok=True); im.save(OUT/fn,"JPEG",quality=94,optimize=True); im.save(OUT/"latest.jpg","JPEG",quality=94,optimize=True)
    from quote_source import generate_hashtags
    meta={"quote":q,"template":t.name,"filename":fn,"latest_filename":"latest.jpg","generated_at_utc":now.isoformat(),"quote_source":src,"priority_line":line,"hashtags":generate_hashtags(q)}
    (OUT/"latest.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False))
if __name__=="__main__": main()
