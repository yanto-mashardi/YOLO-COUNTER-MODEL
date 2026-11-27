import json,csv,os,tempfile
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
def atomic(path,write):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="") as f:
            write(f);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def save_profile(path,values):
    data={k:v for k,v in values.items() if k not in ("token","mode")}
    if data.get("source","").startswith("rtsp://"):
        u=urlsplit(data["source"])
        data["source"]=urlunsplit((u.scheme,u.netloc.rsplit("@",1)[-1],u.path,"",""))
    atomic(path,lambda f:json.dump(data,f,indent=2))
def load_profile(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}
def metrics(mc,mm,c,m):
    if min(mc,mm,c,m)<0:raise ValueError("Negative count")
    return abs(c-mc),abs(m-mm),100*(abs(c-mc)+abs(m-mm))/(mc+mm) if mc+mm else None
def archive(store,port,folder):
    days={}
    for ts,c,m in store.rows(port):days.setdefault(ts[:10],[]).append([ts[11:].split("+")[0],str(m),str(c)])
    for day,rows in days.items():
        path=Path(folder)/port.upper()/("VEHICLES_"+port.upper()+"_"+day+".csv")
        rows=[["jam","jumlah_motor","jumlah_mobil"]]+rows
        if path.exists():
            with path.open(encoding="utf-8",newline="") as f:old=list(csv.reader(f))
            if old!=rows[:len(old)]:raise ValueError("Archive conflict")
            if old==rows:continue
        atomic(path,lambda f:csv.writer(f).writerows(rows))
