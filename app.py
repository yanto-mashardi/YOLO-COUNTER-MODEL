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
    self.line_button=ttk.Button(self.frame,text="Atur garis hitung pada video",command=self.edit_line);self.line_button.pack(fill="x",pady=4)
    self.calibration_source=None;self.calibrating=False
    self.vars["source"].trace_add("write",lambda *_:setattr(self,"calibration_source",None))
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
 def edit_line(self):
    if self.calibrating or (self.worker and self.worker.is_alive()) or (self.sender and self.sender.is_alive()):
        messagebox.showinfo("Pengaturan garis","Hentikan pemrosesan terlebih dahulu.");return
    source=self.vars["source"].get().strip()
    if not source:
        messagebox.showwarning("Sumber video","Masukkan RTSP atau pilih file video dahulu.");return
    self.calibrating=True;self.line_button.configure(state="disabled")
    result=queue.Queue(1)
    def read():
        cap=None
        try:
            cap=cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,8000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,8000])
            ok,frame=cap.read()
            if not ok:raise RuntimeError("No frame")
            result.put(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)))
        except Exception:result.put(None)
        finally:
            if cap is not None:cap.release()
    threading.Thread(target=read,daemon=True).start()
    self.info.set("Membaca frame untuk pengaturan garis...")
    def poll():
        try:im=result.get_nowait()
        except queue.Empty:self.frame.after(100,poll);return
        self.calibrating=False;self.line_button.configure(state="normal")
        if im is None:
            self.info.set("Preview gagal")
            messagebox.showerror("Preview","Frame tidak dapat dibaca. Periksa sumber video.");return
        if source!=self.vars["source"].get().strip():return
        self.line_dialog(im,source)
    self.frame.after(100,poll)
 def line_dialog(self,im,source):
    win=tk.Toplevel(self.frame);win.title("Atur garis hitung — "+self.port.upper());win.transient(self.frame.winfo_toplevel())
    im.thumbnail((min(1100,win.winfo_screenwidth()-100),min(620,win.winfo_screenheight()-240)))
    w,h=im.size
    photo=ImageTk.PhotoImage(im,master=win)
    ttk.Label(win,text="Klik titik awal dan titik akhir garis. Panah menunjukkan arah kendaraan masuk.",wraplength=w).pack(padx=8,pady=6)
    canvas=tk.Canvas(win,width=w,height=h,highlightthickness=0,cursor="crosshair");canvas.pack(padx=8)
    canvas.create_image(0,0,image=photo,anchor="nw");canvas.image=photo
    points=[];direction=tk.IntVar(value=int(self.vars["direction"].get()))
    try:
        a=list(map(float,self.vars["line"].get().split(",")))
        if len(a)==4 and all(0<=v<=1 for v in a) and a[:2]!=a[2:]:points[:]=[(a[0],a[1]),(a[2],a[3])]
    except ValueError:pass
    def draw():
        canvas.delete("overlay")
        for x,y in points:
            canvas.create_oval(x*w-5,y*h-5,x*w+5,y*h+5,fill="#ffe000",outline="black",tags="overlay")
        if len(points)==2:
            (x1,y1),(x2,y2)=points
            canvas.create_line(x1*w,y1*h,x2*w,y2*h,fill="#ffe000",width=3,tags="overlay")
            # Direction is normal to the line in normalized image coordinates.
            dx,dy=x2-x1,y2-y1;n=(dx*dx+dy*dy)**.5
            if n:
                mx,my=(x1+x2)*w/2,(y1+y2)*h/2
                vx,vy=-dy*w/n*direction.get(),dx*h/n*direction.get()
                scale=36/max(1,(vx*vx+vy*vy)**.5);vx*=scale;vy*=scale
                canvas.create_line(mx-vx,my-vy,mx+vx,my+vy,fill="#00ffff",width=4,arrow="last",tags="overlay")
    def click(e):
        p=(min(1,max(0,e.x/w)),min(1,max(0,e.y/h)))
        if len(points)==2:points.clear()
        if points and ((p[0]-points[0][0])**2+(p[1]-points[0][1])**2)**.5<.01:return
        points.append(p);draw()
    def save():
        if len(points)!=2:
            messagebox.showwarning("Garis","Tentukan dua titik garis.",parent=win);return
        if source!=self.vars["source"].get().strip():
            messagebox.showwarning("Sumber","Sumber video berubah. Buka pengaturan ulang.",parent=win);win.destroy();return
        self.vars["line"].set(",".join(f"{v:.6f}" for p in points for v in p))
        self.vars["direction"].set(str(direction.get()));self.calibration_source=source
        draw()
        # Render saved calibration in the main panel without running inference.
        preview=im.copy()
        from PIL import ImageDraw
        pen=ImageDraw.Draw(preview);pen.line([(x*w,y*h) for x,y in points],fill="yellow",width=3)
        preview.thumbnail((600,340));self.photo=ImageTk.PhotoImage(preview);self.preview.configure(image=self.photo,text="")
        self.info.set("Garis disimpan — siap Start");win.destroy()
    canvas.bind("<Button-1>",click)
    bar=ttk.Frame(win);bar.pack(fill="x",padx=8,pady=8)
    ttk.Button(bar,text="Ulangi garis",command=lambda:(points.clear(),draw())).pack(side="left",padx=3)
    ttk.Button(bar,text="Balik arah masuk",command=lambda:(direction.set(-direction.get()),draw())).pack(side="left",padx=3)
    ttk.Button(bar,text="Batal",command=win.destroy).pack(side="right",padx=3)
    ttk.Button(bar,text="Simpan garis",command=save).pack(side="right",padx=3)
    draw();win.grab_set()
 def start(self):
    if self.calibrating:return
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
            if self.calibration_source!=c["source"].strip():
                messagebox.showwarning("Kalibrasi","Atur dan simpan garis untuk sumber video ini sebelum mode operasional.");return
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
                for xy,tid,cls,conf in zip(result.boxes.xyxy.cpu().tolist(),result.boxes.id.int().cpu().tolist(),result.boxes.cls.int().cpu().tolist(),result.boxes.conf.cpu().tolist()):
                    x1,y1,x2,y2=xy;kind=counter.update(tid,((x1+x2)/(2*w),y2/h),classes[cls],frame_id,conf)
                    if kind=="car":car+=1;changed=True
                    elif kind=="motor":motor+=1;changed=True
                    if kind:
                        tid0,raw,stable,votes=counter.last_event
                        print(f'COUNT {self.port} ID={tid0} frame={frame_id} raw={raw} counted={stable} votes={votes}',flush=True)
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
