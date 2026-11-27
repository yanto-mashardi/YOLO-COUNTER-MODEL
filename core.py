"""Pure counting geometry, persistent snapshots and BIMA2 HTTPS client."""
import sqlite3, json, urllib.request, urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
WIB=ZoneInfo("Asia/Jakarta")
PORTS=("bengkalis","pakning")
def now(): return datetime.now(WIB)
class Crossing:
    def __init__(self,a,b,direction=1,margin=.008):
        if a==b or direction not in (-1,1): raise ValueError("Invalid line")
        self.a,self.b,self.direction,self.margin=a,b,direction,margin
        self.tracks={}
    def update(self,tid,p,kind,frame):
        ax,ay=self.a; dx=self.b[0]-ax;dy=self.b[1]-ay
        length=(dx*dx+dy*dy)**.5
        distance=(dx*(p[1]-ay)-dy*(p[0]-ax))/length
        side=1 if distance>self.margin else -1 if distance < -self.margin else 0
        old=self.tracks.get(tid)
        if not old:
            if side:self.tracks[tid]=(side,p,False,frame)
            return None
        prev,q,done,last=old
        if not side:return None
        hit=False
        if prev!=side and side==self.direction and not done and frame-last<=30:
            qd=(dx*(q[1]-ay)-dy*(q[0]-ax))/length
            t=qd/(qd-distance)
            x=q[0]+t*(p[0]-q[0]);y=q[1]+t*(p[1]-q[1])
            u=((x-ax)*dx+(y-ay)*dy)/(length*length)
            hit=0<=u<=1
        self.tracks[tid]=(side,p,done or hit,frame)
        return kind if hit else None
    def prune(self,frame):
        self.tracks={k:v for k,v in self.tracks.items() if frame-v[3]<600}
class Store:
    def __init__(self,path):
        self.path=path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS snapshots(port TEXT, ts TEXT, car INTEGER, motor INTEGER, PRIMARY KEY(port,ts))")
    def connect(self):return sqlite3.connect(self.path,timeout=10)
    def counts(self,port,day):
        with self.connect() as db:
            r=db.execute("SELECT car,motor FROM snapshots WHERE port=? AND substr(ts,1,10)=? ORDER BY ts DESC LIMIT 1",(port,day)).fetchone()
            return r or (0,0)
    def snapshot(self,port,car,motor,ts):
        with self.connect() as db:
            db.execute("INSERT INTO snapshots VALUES(?,?,?,?)",(port,ts.isoformat(),car,motor))
    def rows(self,port):
        with self.connect() as db:
            return db.execute("SELECT ts,car,motor FROM snapshots WHERE port=? ORDER BY ts",(port,)).fetchall()
def request(url,token,body=None):
    if urllib.parse.urlsplit(url).scheme!="https":raise ValueError("HTTPS required")
    headers={"Authorization":"Bearer "+token}
    if body is not None:headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    # Do not follow redirects with credentials.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*a,**k):return None
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=8) as res:return json.load(res)
def payload(device,ts,car,motor):
    t=datetime.fromisoformat(ts).astimezone(WIB)
    return {"device":device,"mode":"OBSERVED","state":{"tanggal":t.date().isoformat(),"jam":t.time().replace(tzinfo=None).isoformat(),"jumlah_mobil":car,"jumlah_motor":motor}}
def send_pending(store,port,base,device,token):
    endpoint=base.rstrip("/")+"/api/vehicles/"+port
    cursor=request(endpoint+"/resume?"+urllib.parse.urlencode({"device":device}),token)
    cutoff=datetime.fromisoformat(cursor["cutoff"])
    last=datetime.fromisoformat(cursor["last_ts"]) if cursor["last_ts"] else None
    accepted=None
    for ts,c,m in store.rows(port):
        t=datetime.fromisoformat(ts)
        if t>=cutoff and (last is None or t>last):
            accepted=request(endpoint,token,payload(device,ts,c,m))
            if not accepted.get("accepted"):raise ValueError("No acknowledgement")
            last=t
    return accepted
