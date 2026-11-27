"""Windows validation-first counter. No VPS writes unless explicitly armed."""
import os
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS","rtsp_transport;tcp")
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import threading,time,queue,json,csv,uuid
from pathlib import Path
import cv2,torch
from PIL import Image,ImageTk
from ultralytics import YOLO
from core import Crossing,Store,now,send_pending
ROOT=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"YOLO_COUNTER_MODEL"
ROOT.mkdir(parents=True,exist_ok=True)
BASE="https://eta-etd.gudang-apps.my.id"
MODELS=["yolov8n.pt","yolov8s.pt","yolov8m.pt","yolo11n.pt","yolo11s.pt","yolo11m.pt"]
class Panel:
 def __init__(self,parent,port):
    self.port=port;self.stop=threading.Event();self.worker=None;self.sender=None
    self.frames=queue.Queue(1);self.status=queue.Queue();self.live=threading.Event()
    self.vars={}
    self.frame=ttk.LabelFrame(parent,text=port.upper(),padding=8);self.frame.pack(side="left",fill="both",expand=True,padx=5)
    def field(k,label,value="",opts=None,secret=False):
        ttk.Label(self.frame,text=label).pack(anchor="w")
        v=tk.StringVar(value=value);self.vars[k]=v
        if opts: w=ttk.Combobox(self.frame,textvariable=v,values=opts,state="readonly")
        else:w=ttk.Entry(self.frame,textvariable=v,show="*" if secret else "")
        w.pack(fill="x")
    field("source","RTSP URL / file video","",secret=True)
    ttk.Button(self.frame,text="Pilih video lokal",command=lambda:self.vars["source"].set(filedialog.askopenfilename())).pack(anchor="w")
    field("model","Model YOLO","yolo11n.pt",MODELS)
    ttk.Button(self.frame,text="Pilih model .pt terpercaya",command=self.custom).pack(anchor="w")
    field("device","Perangkat inferensi","auto",["auto","cpu","0"])
    field("tracker","Tracker","bytetrack.yaml",["bytetrack.yaml","botsort.yaml"])
    field("conf","Confidence","0.35")
    field("iou","IoU","0.5")
    field("size","Input size","640",["320","480","640","960"])
    field("line","Garis x1,y1,x2,y2 (0-1)",".1,.5,.9,.5")
    field("direction","Arah masuk","1",["1","-1"])
    field("mode","Mode","VALIDATION",["VALIDATION","OPERATIONAL"])
    field("identity","Identitas publisher",os.environ.get("COMPUTERNAME","PC-KAMPUS-YOLO"))
    field("token","Token resmi per pelabuhan","",secret=True)
    field("archive","Folder ekspor CSV / Google Drive (opsional)","")
    ttk.Button(self.frame,text="Pilih folder arsip",command=lambda:self.vars["archive"].set(filedialog.askdirectory())).pack(anchor="w")
    row=ttk.Frame(self.frame);row.pack(fill="x",pady=4)
    for name,fn in [("Start",self.start),("Stop",self.halt),("Ekspor CSV",self.export)]:
        ttk.Button(row,text=name,command=fn).pack(side="left",expand=True,fill="x")
    self.preview=ttk.Label(self.frame,text="Preview belum aktif");self.preview.pack()
    self.info=tk.StringVar(value="STOPPED");ttk.Label(self.frame,textvariable=self.info,wraplength=500).pack(anchor="w")
    self.net=tk.StringVar(value="PUBLISH OFF");ttk.Label(self.frame,textvariable=self.net,wraplength=500).pack(anchor="w")
    self.store=None
    self.frame.after(100,self.tick)
 def custom(self):
    p=filedialog.askopenfilename(filetypes=[("Trusted YOLO weights","*.pt")])
    if p:self.vars["model"].set(p)
 def start(self):
    if self.worker and self.worker.is_alive():return
    if self.sender and self.sender.is_alive():return
    c={k:v.get() for k,v in self.vars.items()}
    try:
        assert c["source"] and c["model"]
        a=list(map(float,c["line"].split(",")));assert len(a)==4 and all(0<=x<=1 for x in a)
        assert 0<float(c["conf"])<=1 and 0<float(c["iou"])<=1
        Crossing(a[:2],a[2:],int(c["direction"]))
        if c["device"]=="0" and not torch.cuda.is_available():raise ValueError("CUDA unavailable")
        if c["mode"]=="OPERATIONAL":
            assert c["source"].startswith("rtsp://") and c["token"] and c["identity"].strip()
            if not messagebox.askyesno("Commissioning","Aktifkan pengiriman resmi? Pastikan garis dan arah tervalidasi, publisher Manager cocok, counter awal direkonsiliasi, dan tidak ada pengirim lain."):return
    except Exception:
        messagebox.showerror("Konfigurasi","Periksa sumber, parameter, perangkat, dan token.");return
    self.stop.clear();self.live.clear()
    name="official" if c["mode"]=="OPERATIONAL" else "validation_"+uuid.uuid4().hex
    self.store=Store(ROOT/(name+"_"+self.port+".sqlite"))
    self.worker=threading.Thread(target=self.run,args=(c,a,self.store),daemon=True);self.worker.start()
    if c["mode"]=="OPERATIONAL":
        self.sender=threading.Thread(target=self.publish,args=(c,self.store),daemon=True);self.sender.start()
    else:self.net.set("VALIDATION: tidak mengirim ke VPS")
 def halt(self):
    self.stop.set();self.live.clear()
 def tick(self):
    try:
        while True:
            kind,text=self.status.get_nowait()
            (self.net if kind=="net" else self.info).set(text)
    except queue.Empty:pass
    try:
        im=self.frames.get_nowait();self.photo=ImageTk.PhotoImage(im);self.preview.configure(image=self.photo,text="")
    except queue.Empty:pass
    self.frame.after(100,self.tick)
 def putframe(self,frame):
    im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));im.thumbnail((600,340))
    try:self.frames.get_nowait()
    except queue.Empty:pass
    self.frames.put_nowait(im)
 def run(self,c,a,store):
    cap=None
    try:
        model=YOLO(c["model"]);names=model.names
        mapping={"car":"car","truck":"car","bus":"car","motorcycle":"motor"}
        classes={int(k):mapping[v.lower()] for k,v in names.items() if v.lower() in mapping}
        if not classes:raise ValueError("Model requires COCO vehicle names")
        device=("0" if torch.cuda.is_available() else "cpu") if c["device"]=="auto" else c["device"]
        cap=cv2.VideoCapture(c["source"],cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,8000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,8000])
        if not cap.isOpened():raise RuntimeError("Source unavailable")
        counter=Crossing(a[:2],a[2:],int(c["direction"]));day=now().date().isoformat()
        car,motor=store.counts(self.port,day);frame_id=0;last=0;started=time.monotonic()
        while not self.stop.is_set():
            ok,frame=cap.read()
            if not ok:
                self.status.put(("info","END / STREAM LOST — restart after checking gap"));break
            t=now();newday=t.date().isoformat()
            if newday!=day:day=newday;car,motor=store.counts(self.port,day)
            result=model.track(frame,persist=True,tracker=c["tracker"],classes=list(classes),conf=float(c["conf"]),iou=float(c["iou"]),imgsz=int(c["size"]),device=device,verbose=False)[0]
            frame_id+=1;h,w=frame.shape[:2];changed=False
            if result.boxes.id is not None:
                for xy,tid,cls in zip(result.boxes.xyxy.cpu().tolist(),result.boxes.id.int().cpu().tolist(),result.boxes.cls.int().cpu().tolist()):
                    x1,y1,x2,y2=xy;kind=counter.update(tid,((x1+x2)/(2*w),y2/h),classes[cls],frame_id)
                    if kind=="car":car+=1;changed=True
                    elif kind=="motor":motor+=1;changed=True
            counter.prune(frame_id)
            if changed or time.monotonic()-last>=10:
                store.snapshot(self.port,car,motor,t);last=time.monotonic()
            self.live.set()
            annotated=result.plot()
            cv2.line(annotated,(int(a[0]*w),int(a[1]*h)),(int(a[2]*w),int(a[3]*h)),(0,255,255),3)
            cv2.putText(annotated,f"Mobil {car} | Motor {motor}",(12,30),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,255,255),2)
            self.putframe(annotated)
            self.status.put(("info",f"{c['mode']} | {device} | {frame_id/max(.01,time.monotonic()-started):.1f} FPS | Mobil {car} | Motor {motor}"))
    except Exception as e:self.status.put(("info","ERROR: "+type(e).__name__+" — check source/model/device"))
    finally:
        self.live.clear();self.stop.set()
        if cap is not None:cap.release()
 def publish(self,c,store):
    while not self.stop.wait(3):
        if not self.live.is_set():continue
        try:
            ack=send_pending(store,self.port,BASE,c["identity"],c["token"])
            if ack:self.status.put(("net",f"ACK VPS | Mobil {ack['official_car']} | Motor {ack['official_motor']}"))
            else:self.status.put(("net","Menunggu snapshot baru setelah cutover"))
        except Exception as e:self.status.put(("net","PUBLISH ERROR: "+type(e).__name__+" — data tersimpan lokal"))
 def export(self):
    if not self.store:return
    folder=self.vars["archive"].get() or str(ROOT/"exports")
    p=Path(folder);p.mkdir(parents=True,exist_ok=True)
    name=f"{self.port}_{os.environ.get('COMPUTERNAME','PC')}_{now().strftime('%Y%m%d_%H%M%S_%f')}.csv"
    with (p/name).open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["timestamp_wib","jumlah_mobil","jumlah_motor"]);w.writerows(self.store.rows(self.port))
    messagebox.showinfo("Ekspor",str(p/name))
def main():
 root=tk.Tk();root.title("BIMA2 | YOLO Counter Model");root.geometry("1250x950")
 ttk.Label(root,text="YOLO Counter Model — Bengkalis & Pakning",font=("Segoe UI",18,"bold")).pack(pady=8)
 canvas=tk.Canvas(root);scroll=ttk.Scrollbar(root,orient="vertical",command=canvas.yview);scroll.pack(side="right",fill="y");canvas.pack(fill="both",expand=True);canvas.configure(yscrollcommand=scroll.set)
 body=ttk.Frame(canvas);win=canvas.create_window((0,0),window=body,anchor="nw");body.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")));canvas.bind("<Configure>",lambda e:canvas.itemconfigure(win,width=e.width))
 panels=[Panel(body,p) for p in ("bengkalis","pakning")]
 def close():
    for p in panels:p.halt()
    root.destroy()
 root.protocol("WM_DELETE_WINDOW",close);root.mainloop()
if __name__=="__main__":main()
