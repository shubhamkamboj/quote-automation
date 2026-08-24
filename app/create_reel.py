import json,random,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"generated"; AUDIO=ROOT/"audio"; META=OUT/"latest.json"
def main():
 m=json.loads(META.read_text(encoding="utf-8")); img=OUT/m["filename"]; tracks=sorted(AUDIO.glob("*.mp3"))
 if not img.exists(): raise RuntimeError("Image not found")
 if not tracks: raise RuntimeError("No audio tracks")
 track=random.SystemRandom().choice(tracks); reel=OUT/(Path(m["filename"]).stem.replace("quote-","reel-",1)+".mp4")
 fc=("[0:v]split=2[bg0][fg0];[bg0]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=#efe7d8,boxblur=12:1[bg];"
     "[fg0]scale=1080:1800,zoompan=z='min(zoom+0.0008,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=250:s=1080x1800:fps=25,pad=1080:1920:0:60:color=#efe7d8[fg];[bg][fg]overlay=0:0")
 subprocess.run(["ffmpeg","-y","-loglevel","error","-loop","1","-i",str(img),"-i",str(track),"-filter_complex",fc,"-t","10","-map","0:v","-map","1:a","-c:v","libx264","-pix_fmt","yuv420p","-r","25","-c:a","aac","-ar","48000","-b:a","128k","-shortest","-movflags","+faststart",str(reel)],check=True)
 m["reel_filename"]=reel.name; m["audio_track"]=track.name; META.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8")
 print(reel)
if __name__=="__main__":
 try: main()
 except Exception as e: print("ERROR:",e,file=sys.stderr); sys.exit(1)
