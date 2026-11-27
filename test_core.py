import unittest,tempfile
from pathlib import Path
from core import Crossing,Store,now,payload,roi_bounds,roi_pixels,inside_roi,vehicle_group,add_count
class Tests(unittest.TestCase):
 def test_crossing(self):
    c=Crossing((.1,.5),(.9,.5))
    self.assertIsNone(c.update(1,(.5,.3),"car",1))
    self.assertEqual(c.update(1,(.5,.7),"car",2),"car")
    self.assertIsNone(c.update(1,(.5,.3),"car",3))
    self.assertIsNone(c.update(1,(.5,.7),"car",4))
 def test_outside(self):
    c=Crossing((.2,.5),(.8,.5))
    c.update(1,(.1,.3),"car",1)
    self.assertIsNone(c.update(1,(.1,.7),"car",2))
 def test_reverse(self):
    c=Crossing((0,.5),(1,.5))
    c.update(1,(.5,.7),"motor",1)
    self.assertIsNone(c.update(1,(.5,.3),"motor",2))
 def test_motor_crossing(self):
    c=Crossing((0,.5),(1,.5))
    c.update(74,(.5,.3),"motor",1,.8)
    self.assertEqual(c.update(74,(.5,.7),"motor",2,.53),"motor")
 def test_class_flip(self):
    c=Crossing((0,.5),(1,.5))
    c.update(74,(.5,.2),"motor",1,.8)
    c.update(74,(.5,.3),"motor",2,.7)
    self.assertEqual(c.update(74,(.5,.7),"car",3,.6),"motor")
    self.assertEqual(c.last_event[:3],(74,"car","motor"))
 def test_car_with_motor_noise(self):
    c=Crossing((0,.5),(1,.5))
    c.update(12,(.5,.2),"car",1,.9)
    c.update(12,(.5,.3),"car",2,.8)
    self.assertEqual(c.update(12,(.5,.7),"motor",3,.5),"car")
 def test_independent_counters(self):
    car,motor=0,0
    for label in ("car","motorcycle","motorcycle","truck","bus"):
     car,motor=add_count(car,motor,vehicle_group(label))
    self.assertEqual((car,motor),(3,2))
 def test_roi_coordinates(self):
    r=roi_bounds((.8,.9,.2,.1))
    self.assertEqual(roi_pixels(r,1000,500),(200,50,800,450))
    self.assertTrue(inside_roi((.5,.5),r))
    self.assertFalse(inside_roi((.1,.5),r))
 def test_roi_invalid(self):
    with self.assertRaises(ValueError):roi_bounds((.2,.2,.2,.8))
 def test_store(self):
    with tempfile.TemporaryDirectory() as d:
     p=Path(d)/"test.sqlite";s=Store(p);t=now();s.snapshot("pakning",3,4,t)
     self.assertEqual(Store(p).counts("pakning",t.date().isoformat()),(3,4))
     self.assertEqual(payload("PC",t.isoformat(),3,4)["state"]["jumlah_motor"],4)
 def test_metrics(self):
    from support import metrics
    self.assertEqual(metrics(10,10,9,11),(1,1,10))
    self.assertIsNone(metrics(0,0,0,0)[2])
 def test_profile(self):
    from support import save_profile,load_profile
    with tempfile.TemporaryDirectory() as d:
     p=Path(d)/"p.json";save_profile(p,{"source":"rtsp://u:secret@host/live/a","token":"secret","mode":"OPERATIONAL"})
     self.assertEqual(load_profile(p)["source"],"rtsp://host/live/a")
     self.assertNotIn("secret",p.read_text())
 def test_archive(self):
    from support import archive
    with tempfile.TemporaryDirectory() as d:
     s=Store(Path(d)/"x.sqlite");t=now();s.snapshot("pakning",3,4,t)
     archive(s,"pakning",d);archive(s,"pakning",d)
     p=Path(d)/"PAKNING"/("VEHICLES_PAKNING_"+t.date().isoformat()+".csv")
     self.assertIn("jam,jumlah_motor,jumlah_mobil",p.read_text())
 def test_youtube_urls(self):
    from video_source import youtube_url
    expected="https://www.youtube.com/watch?v=kC4sXn8pTco"
    for u in (expected,"https://youtu.be/kC4sXn8pTco","https://www.youtube.com/embed/kC4sXn8pTco?si=x",'<iframe src="https://www.youtube.com/embed/kC4sXn8pTco"></iframe>'):
     self.assertEqual(youtube_url(u),expected)
    with self.assertRaises(ValueError):youtube_url("https://example.com/watch?v=kC4sXn8pTco")
if __name__=="__main__":unittest.main()
