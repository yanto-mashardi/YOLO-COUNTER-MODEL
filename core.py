"""Pure counting geometry, persistent snapshots and BIMA2 HTTPS client."""
import sqlite3, json, urllib.request, urllib.parse
from contextlib import contextmanager
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
        self.votes={}
        self.last_event=None
    def update(self,tid,p,kind,frame,confidence=1.0):
        self.last_event=None
        if kind not in ('car','motor'):raise ValueError('Unknown vehicle group')
        votes=self.votes.setdefault(tid,{'car':0.0,'motor':0.0})
        votes[kind]+=float(confidence)
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
        if hit:
            stable=max(votes,key=lambda k:(votes[k],k==kind))
            self.last_event=(tid,kind,stable,dict(votes))
            return stable
        return None
    def prune(self,frame):
        self.tracks={k:v for k,v in self.tracks.items() if frame-v[3]<600}
        self.votes={k:v for k,v in self.votes.items() if k in self.tracks}
def roi_bounds(values):
    x1,y1,x2,y2=map(float,values)
    x1,x2=sorted((x1,x2));y1,y2=sorted((y1,y2))
    if not (0<=x1<x2<=1 and 0<=y1<y2<=1 and x2-x1>=.03 and y2-y1>=.03):
        raise ValueError("Invalid ROI")
    return x1,y1,x2,y2
def roi_pixels(roi,w,h):
    import math
    x1,y1,x2,y2=roi_bounds(roi)
    return int(x1*w),int(y1*h),min(w,math.ceil(x2*w)),min(h,math.ceil(y2*h))
def inside_roi(point,roi):
    x,y=point;x1,y1,x2,y2=roi
    return x1<=x<=x2 and y1<=y<=y2
def vehicle_group(name):
    return {"car":"car","truck":"car","bus":"car","motorcycle":"motor"}.get(name.lower())
def add_count(car,motor,kind):
    if kind=="car":return car+1,motor
    if kind=="motor":return car,motor+1
    if kind is None:return car,motor
    raise ValueError("Unknown counted class")
class Store:
    def __init__(self,path):
        self.path=path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS snapshots(port TEXT, ts TEXT, car INTEGER, motor INTEGER, PRIMARY KEY(port,ts))")
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()
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
