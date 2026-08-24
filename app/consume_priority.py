import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 m=json.loads((ROOT/"generated/latest.json").read_text(encoding="utf-8"))
 if m.get("quote_source")!="priority": print("No priority to consume."); return
 line=m.get("priority_line")
 if not line: raise RuntimeError("Priority line missing.")
 from quote_source import remove_priority_quote
 remove_priority_quote(int(line)); print("Priority consumed.")
if __name__=="__main__": main()
