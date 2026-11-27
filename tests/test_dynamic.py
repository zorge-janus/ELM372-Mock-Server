import unittest

from dynamic import dropout, encode, values
from elm_mock import Elm, read_scenario
from dataset import load_dataset

class DynamicClimateTests(unittest.TestCase):
    def setUp(self):
        self.s=read_scenario("climate_ddt_0456")
        self.fast=read_scenario("climate_faults_fast")

    def test_repeat(self):
        self.assertEqual(values(35,self.s),values(275,self.s))

    def test_modes(self):
        self.assertEqual(values(35,self.s)["Mode AUTO"],"ON")
        self.assertEqual(values(150,self.s)["Mode AC"],"ON")
        self.assertEqual(values(40,self.s)["Commande Relais CTP3"],"ON")
        self.assertEqual(values(130,self.s)["Commande Relais CTP1"],"OFF")

    def test_active_and_stored_faults(self):
        self.assertEqual(values(185,self.s)["CC présent capteur freon condenseur"],"Defaut")
        self.assertEqual(values(205,self.s)["CC présent capteur freon condenseur"],"OK")
        self.assertEqual(values(205,self.s)["CC mémo capteur freon condenseur"],"Defaut")
        self.assertEqual(values(215,self.s)["CO présent sonde évapo"],"Defaut")
        self.assertEqual(values(235,self.s)["CO présent sonde évapo"],"OK")
        self.assertEqual(values(235,self.s)["CO mémo sonde évapo"],"Defaut")

    def test_network_and_dropout(self):
        self.assertEqual(values(215,self.s)["ABS absent"],"Absent")
        self.assertEqual(values(235,self.s)["ABS absent"],"Présent")
        self.assertEqual(values(235,self.s)["ABS absent - compteur panne mémo"],3)
        self.assertTrue(dropout("21C1",215,self.s))
        self.assertFalse(dropout("21C1",225,self.s))
        self.assertFalse(dropout("21C0",215,self.s))

    def test_fast_cycle(self):
        self.assertEqual(values(185/4,self.fast)["CC présent capteur freon condenseur"],"Defaut")
        self.assertTrue(dropout("21C1",215/4,self.fast))
        self.assertEqual(values(60,self.fast),values(0,self.fast))

    def test_nominal_no_injected_fault(self):
        nominal=read_scenario("climate_nominal")
        for t in (0,185,205,215,235):
            self.assertEqual(values(t,nominal)["CC présent capteur freon condenseur"],"OK")
            self.assertEqual(values(t,nominal)["ABS absent"],"Présent")

    def test_encode_fault_bit_positions(self):
        d={"endian":"Big",
           "requests":[{"sentbytes":"21C0","receivebyte_dataitems":{
             "CC présent capteur freon condenseur":{"firstbyte":3,"bitoffset":5},
             "CC mémo capteur freon condenseur":{"firstbyte":15,"bitoffset":5}}}],
           "data":{name:{"bitscount":1,"lists":{"0":"OK","1":"Defaut"}}
               for name in ("CC présent capteur freon condenseur","CC mémo capteur freon condenseur")},
           "devices":[{"name":"Pressure sensor","devicedata":{
             "CC présent capteur freon condenseur":"1",
             "CC mémo capteur freon condenseur":"1"}}]}
        raw="61 C0"+" 00"*13
        changed=bytes.fromhex(encode(d,"21C0",raw,185,self.s))
        self.assertEqual(changed[2],4)
        self.assertEqual(changed[14],4)
        after=bytes.fromhex(encode(d,"21C0",raw,205,self.s))
        self.assertEqual(after[2],0)
        self.assertEqual(after[14],4)

    def test_elm_dynamic_without_wallclock_wait(self):
        d={"endian":"Big","requests":[{"sentbytes":"21C0",
             "receivebyte_dataitems":{"CC présent capteur freon condenseur":{"firstbyte":3,"bitoffset":5}}}],
             "data":{"CC présent capteur freon condenseur":{"bitscount":1,"lists":{"0":"OK","1":"Defaut"}}},
             "devices":[{"name":"Pressure","devicedata":{"CC présent capteur freon condenseur":"1"}}]}
        elm=Elm(load_dataset(),speed=0,definition=d,scenario=self.s)
        elm.reply("ATSP5")
        elm.reply("ATSH8129F1")
        elm.reply("ATFI")
        elm.started-=185
        elm.climate_started=True
        reply=elm.reply("21C0").decode()
        self.assertIn("61 C0",reply)
        self.assertEqual(bytes.fromhex(reply.split("\r")[1][:8])[2],4)

if __name__=="__main__":
    unittest.main()
