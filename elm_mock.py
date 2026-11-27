"""Offline ELM327 KWP simulator with scenario files; no vehicle I/O."""
import argparse
import collections
import json
from pathlib import Path
import re
import socketserver
import time

from dataset import load_dataset
from dynamic import dropout, encode

ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / "scenarios"

def list_scenarios():
    return sorted(p.stem for p in SCENARIOS.glob("*.json"))

def read_scenario(name):
    if not re.fullmatch(r"[a-z][a-z0-9_]*",name):
        raise ValueError("Scenario must be a simple name from scenarios/")
    path=SCENARIOS / (name+".json")
    if not path.is_file():
        raise ValueError("Unknown scenario "+name+"; available: "+", ".join(list_scenarios()))
    config=json.loads(path.read_text(encoding="utf-8"))
    if config.get("id") != name or config.get("mode") not in ("replay","dynamic_climate"):
        raise ValueError("Invalid scenario metadata: "+path.name)
    if not 0<float(config.get("clock_rate",1))<=100 or float(config.get("cycle_seconds",240))<=0:
        raise ValueError("Invalid scenario clock")
    return config

class Elm:
    def __init__(self, dataset, speed=.1, definition=None, scenario=None):
        self.ecus=dataset["ecus"]
        self.speed=speed
        self.definition=definition
        self.scenario=scenario or {"id":"replay","mode":"replay"}
        self.indices=collections.Counter()
        self.climate_started=False
        self.started=time.monotonic()
        self.reset()
    def reset(self):
        self.address=None
        self.initialized=False
        self.echo=True
        self.spaces=True
        self.lf=False
        self.last=None
        self.protocol=False
        self.climate_started=False
    def reply(self,line):
        command=re.sub(r"\s+","",line).upper()
        if not command:
            if self.last is None:
                return b">"
            command=self.last
        echo=self.echo
        self.last=command
        delay=20
        if command=="ATZ":
            self.reset()
            out="ELM327 v1.5"
            delay=825
        elif command=="ATI":
            out="ELM327 v1.5"
        elif command=="ATRV":
            out="14.2V"
        elif command=="ATE0":
            self.echo=False
            out="OK"
        elif command=="ATE1":
            self.echo=True
            out="OK"
        elif command in ("ATL0","ATL1"):
            self.lf=command.endswith("1")
            out="OK"
        elif command in ("ATS0","ATS1"):
            self.spaces=command.endswith("1")
            out="OK"
        elif command in ("ATH0","ATAT0","ATSTFF"):
            out="OK"
        elif command=="ATSP5":
            self.protocol=True
            self.initialized=False
            out="OK"
        elif command=="ATPC":
            self.initialized=False
            self.climate_started=False
            out="OK"
        elif re.fullmatch(r"ATSH81[0-9A-F]{2}F1",command):
            self.address=command[6:8]
            self.initialized=False
            out="OK"
        elif command=="ATFI":
            self.initialized=self.protocol and self.address in self.ecus
            out="BUS INIT: OK" if self.initialized else "BUS INIT: ERROR"
            delay=430
        elif command=="ATDP":
            out="ISO 14230-4 (KWP FAST)" if self.protocol else "AUTO"
        elif command=="ATDPN":
            out="5" if self.protocol else "0"
        elif command.startswith("AT"):
            out="?"
        elif not re.fullmatch(r"(?:21[0-9A-F]{2}|22[0-9A-F]{4}|1A[0-9A-F]{2}|17FF00)",command):
            out="?"
        elif not self.initialized:
            out="NO DATA"
            delay=1200
        else:
            samples=self.ecus.get(self.address,{}).get(command,[])
            if samples:
                key=(self.address,command)
                i=self.indices[key]
                self.indices[key]+=1
                entry=samples[i%len(samples)]
                out=entry["raw"]
                delay=entry["ms"]
            else:
                out="NO DATA"
                delay=1200
            if (samples and self.definition is not None
                    and self.scenario["mode"]=="dynamic_climate"
                    and self.address=="29" and command in ("21C0","21C1","21C2","2182")):
                if not self.climate_started:
                    self.started=time.monotonic()
                    self.climate_started=True
                elapsed=time.monotonic()-self.started
                if dropout(command,elapsed,self.scenario):
                    out="NO DATA"
                else:
                    # Use first recorded frame as a stable baseline for all dynamic fields.
                    out=encode(self.definition,command,samples[0]["raw"],elapsed,self.scenario)
            if not self.spaces and re.fullmatch(r"(?:[0-9A-Fa-f]{2}\s*)+",out):
                out="".join(out.split())
        if self.speed:
            time.sleep(delay*self.speed/1000)
        separator="\r\n" if self.lf else "\r"
        print(f"{self.address or '--'} {command} -> {out}",flush=True)
        return ((command+separator if echo else "")+out+separator+">").encode("ascii",errors="replace")

def serve_stream(read,write,elm,stop_on_empty=False):
    pending=bytearray()
    while True:
        data=read()
        if not data:
            if stop_on_empty:
                return
            continue
        for char in data:
            if char==13:
                write(elm.reply(pending.decode("ascii",errors="replace")))
                pending.clear()
            elif char==10:
                continue
            elif len(pending)<1024:
                pending.append(char)
            else:
                pending.clear()
                write(b"?\r>")

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-scenarios",action="store_true",help="Show scenario names and exit")
    parser.add_argument("--scenario",default="climate_ddt_0456",help="Name of scenarios/<name>.json")
    parser.add_argument("--definition",type=Path,help="Local original Clim_J81_Serie_(vers07).json for dynamic CLIMAT")
    parser.add_argument("--data",type=Path,help="Optional external vehicle.json; default bundled sanitized replay corpus")
    parser.add_argument("--serial",help="Incoming Bluetooth SPP COM port, for example COM9")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=35000)
    parser.add_argument("--speed",type=float,default=.1)
    args=parser.parse_args(argv)
    if args.list_scenarios:
        for name in list_scenarios():
            item=read_scenario(name)
            print(f"{name:25} {item.get('description','')}")
        return
    try:
        scenario=read_scenario(args.scenario)
    except ValueError as exc:
        parser.error(str(exc))
    if not 0<=args.speed<=2:
        parser.error("--speed must be 0..2")
    definition=None
    if scenario["mode"]=="dynamic_climate":
        path=args.definition or (ROOT/"Clim_J81_Serie_(vers07).json")
        if not path.is_file():
            parser.error("Scenario requires original Clim_J81_Serie_(vers07).json in project folder or --definition PATH")
        if path.name!="Clim_J81_Serie_(vers07).json":
            parser.error("Expected original Clim_J81_Serie_(vers07).json")
        definition=json.loads(path.read_text(encoding="utf-8-sig"))
        commands={r.get("sentbytes") for r in definition.get("requests",[])}
        if not {"21C0","21C1","21C2","2182"}.issubset(commands):
            parser.error("DDT definition missing required CLIMAT registers")
    dataset=load_dataset(args.data)
    print("OFFLINE MOCK / no vehicle connection",flush=True)
    print("Scenario:",scenario["id"],"mode:",scenario["mode"],"clock rate:",scenario.get("clock_rate",1),flush=True)
    if args.serial:
        try:
            import serial
        except ImportError:
            parser.error("Install pyserial: py -3 -m pip install pyserial")
        with serial.Serial(args.serial,38400,timeout=.2,write_timeout=5) as port:
            print("Bluetooth SPP:",args.serial,flush=True)
            elm=Elm(dataset,args.speed,definition,scenario)
            serve_stream(lambda:port.read(port.in_waiting or 1),port.write,elm)
    else:
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                print("TCP client:",self.client_address,flush=True)
                elm=Elm(dataset,args.speed,definition,scenario)
                try:
                    serve_stream(lambda:self.request.recv(4096),self.request.sendall,elm,True)
                except (ConnectionError,OSError) as exc:
                    print("TCP disconnected:",exc,flush=True)
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address=True
            daemon_threads=True
        with Server((args.host,args.port),Handler) as server:
            print("TCP server:",server.server_address,flush=True)
            server.serve_forever()

if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped")
