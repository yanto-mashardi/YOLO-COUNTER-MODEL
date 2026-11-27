import unittest,tempfile
from pathlib import Path
from core import Crossing,Store,now,payload
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
 def test_store(self):
    with tempfile.TemporaryDirectory() as d:
     p=Path(d)/"test.sqlite";s=Store(p);t=now();s.snapshot("pakning",3,4,t)
     self.assertEqual(Store(p).counts("pakning",t.date().isoformat()),(3,4))
     self.assertEqual(payload("PC",t.isoformat(),3,4)["state"]["jumlah_motor"],4)
if __name__=="__main__":unittest.main()
