"""Synthetic CLIMAT scenario engine. Never accesses a vehicle."""
import math

def in_window(t, window):
    return float(window["start"]) <= t < float(window["end"])

def values(elapsed, scenario):
    t = elapsed * float(scenario.get("clock_rate", 1))
    t %= float(scenario.get("cycle_seconds", 240))
    warm = max(0.0, min(1.0, (t-30)/90)) if t < 210 else max(0.0,(240-t)/30)
    running = 30 <= t < 210
    ac = 120 <= t < 180
    equipment = 180 <= t < 210
    result = {
        "Température intérieure":4+18*warm,
        "Pression Fréon Condenseur":8.4 if ac else 5.2,
        "Consigne PWM GMV habitacle":25+65*(1-warm),
        "Position volet mixage gauche":95-55*warm,
        "Position volet mixage droit":92-50*warm,
        "Position volet distribution pieds":50+15*math.sin(t/25),
        "Position volet ventilation arrière":25+10*math.sin(t/30),
        "Tension Alimentation":14.2+0.15*math.sin(t/12) if running else 12.5,
        "Mode AUTO":"ON" if running else "OFF",
        "Mode AC":"ON" if ac else "OFF",
        "Mode RECY AUTO":"ON" if ac else "OFF",
        "Commande Compresseur":"ON" if ac else "OFF",
        "Pilotage cylindrée compresseur":45 if ac else 0,
        "Commande Chaudière 1":"ON" if equipment else "OFF",
        "Commande Chaudière 2":"ON" if equipment and t<195 else "OFF",
        "Cde relais pulseur 2":"ON" if equipment else "OFF",
        "Commande LARC":"ON" if equipment else "OFF",
        "Info Moteur Tournant":"Tournant" if running else "Non Tournant",
        "ABS absent":"Présent",
        "ABS absent - compteur panne mémo":0,
        "CC présent capteur freon condenseur":"OK",
        "CC mémo capteur freon condenseur":"OK",
        "CO présent sonde évapo":"OK",
        "CO mémo sonde évapo":"OK",
    }
    result.update({"Commande Relais CTP"+str(n):
        "ON" if 30+5*(n-1) <= t < 120-15*(n-1) else "OFF" for n in (1,2,3)})
    for event in scenario.get("field_events", []):
        if in_window(t, event):
            result[event["field"]] = event["value"]
    return result

def dropout(request, elapsed, scenario):
    t = (elapsed*float(scenario.get("clock_rate",1))) % float(scenario.get("cycle_seconds",240))
    return any(x["request"] == request and in_window(t,x) for x in scenario.get("dropouts",[]))

def encode(definition,request,raw,elapsed,scenario):
    data = bytearray.fromhex(raw)
    if data[:2] != bytes.fromhex("61"+request[2:]):
        return raw
    matches = [r for r in definition["requests"] if r.get("sentbytes")==request]
    if len(matches) != 1:
        raise ValueError("Ambiguous DDT register "+request)
    req = matches[0]
    changes = values(elapsed,scenario)
    # Clear all known diagnostic flags before injecting the scenario's known faults.
    # This prevents faults in the historical seed from leaking into the nominal case.
    if request == "21C0":
        flagged = {name for dev in definition.get("devices",[])
                   for name,flag in dev.get("devicedata",{}).items() if str(flag)=="1"}
        for name in flagged:
            if name in req["receivebyte_dataitems"] and definition["data"].get(name,{}).get("bitscount")==1:
                changes[name] = 0
        changes.update({k:v for k,v in values(elapsed,scenario).items() if k in flagged})
    for name,val in changes.items():
        if name not in req["receivebyte_dataitems"]:
            continue
        item = req["receivebyte_dataitems"][name]
        field = definition["data"][name]
        if item.get("endian",req.get("endian",definition.get("endian","Big"))) not in ("Big",""):
            raise ValueError("Unsupported endian "+name)
        bits = int(field.get("bitscount",8))
        first = int(item["firstbyte"])-1
        offset = int(item.get("bitoffset",0))
        length = (bits+offset+7)//8
        if bits<1 or first<2 or not 0<=offset<8 or first+length>len(data):
            raise ValueError("Field outside frame: "+name)
        if isinstance(val,str):
            lists = field.get("lists") or {}
            matched = next((int(k) for k,label in lists.items() if label==val),None)
            if matched is None:
                continue
            val = matched
        elif field.get("scaled"):
            val = round((float(val)*float(field.get("divideby",1))-float(field.get("offset",0)))/float(field.get("step",1)))
        else:
            val = round(float(val))
        signed = bool(field.get("signed"))
        minimum = -(1<<(bits-1)) if signed else 0
        maximum = (1<<(bits-1))-1 if signed else (1<<bits)-1
        val = max(minimum,min(maximum,int(val)))&((1<<bits)-1)
        shift = length*8-offset-bits
        mask = ((1<<bits)-1)<<shift
        original = int.from_bytes(data[first:first+length],"big")
        data[first:first+length] = ((original&~mask)|(val<<shift)).to_bytes(length,"big")
    return data.hex(" ").upper()
