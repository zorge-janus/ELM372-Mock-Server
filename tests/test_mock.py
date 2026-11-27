import unittest

from dataset import load_dataset
from elm_mock import Elm, list_scenarios, read_scenario

class MockProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load_dataset()

    def setUp(self):
        self.elm=Elm(self.data, speed=0, scenario=read_scenario("replay"))

    def send(self, command):
        return self.elm.reply(command).decode("ascii")

    def initialize(self, addr):
        self.send("ATSP5")
        self.send("ATSH81"+addr+"F1")
        self.assertIn("BUS INIT: OK",self.send("ATFI"))

    def test_scans_all_seven_ecus(self):
        self.send("ATZ")
        self.send("ATE0")
        for addr in ("01","2C","29","26","7A","12","0D"):
            self.initialize(addr)
            self.assertIn("61 80",self.send("2180"))
            self.send("ATPC")

    def test_abs_kept(self):
        self.initialize("01")
        for cmd in ("2193","2194","2195","2197"):
            self.assertIn("61 "+cmd[2:],self.send(cmd))
        self.assertIn("57 ",self.send("17FF00"))

    def test_climate_registers(self):
        self.initialize("29")
        for cmd in ("21C0","21C1","21C2","2181","2182"):
            self.assertIn("61 "+cmd[2:],self.send(cmd))

    def test_unsupported_is_safe(self):
        self.initialize("29")
        self.assertIn("?",self.send("14FF00"))
        self.assertIn("?",self.send("308400"))
        self.assertIn("NO DATA",self.send("2193"))
        self.send("ATPC")
        self.assertIn("NO DATA",self.send("21C0"))

    def test_elm_options(self):
        self.assertIn("ELM327",self.send("ATI"))
        self.send("ATE0")
        self.assertNotIn("ATRV",self.send("ATRV"))
        self.assertIn("14.2V",self.send("ATRV"))
        self.send("ATS0")
        self.initialize("01")
        self.assertIn("6193",self.send("2193"))

    def test_history_not_truncated(self):
        self.assertEqual(len(self.data["ecus"]),7)
        self.assertEqual(sum(len(rows) for commands in self.data["ecus"].values() for rows in commands.values()),368)
        raw_vin=bytes.fromhex(self.data["ecus"]["29"]["2181"][0]["raw"])
        self.assertNotIn(b"VF1JK0UA635647506",raw_vin)
        self.assertIn(b"VF1MOCK0000000001",raw_vin)

    def test_scenario_names(self):
        self.assertEqual(list_scenarios(),["climate_ddt_0456","climate_faults_fast","climate_nominal","replay"])
        with self.assertRaises(ValueError):
            read_scenario("../private")
        with self.assertRaises(ValueError):
            read_scenario("missing")

if __name__=="__main__":
    unittest.main()
