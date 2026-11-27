"""Load the compact, VIN-sanitized offline replay corpus."""
import base64
import json
import lzma
from pathlib import Path

CORPUS = Path(__file__).parent / "scenarios" / "replay_corpus.xz.b64"

def load_dataset(path=None):
    if path is not None:
        obj = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if "ecus" not in obj:
            raise ValueError("Dataset must contain ecus")
        return obj
    blob = CORPUS.read_text(encoding="ascii").strip()
    if len(blob) > 200000:
        raise ValueError("Replay corpus too large")
    raw = lzma.decompress(base64.b64decode(blob, validate=True))
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("Replay corpus expanded beyond limit")
    compact = json.loads(raw)
    ecus = {}
    for address, commands in compact.items():
        ecus[address] = {}
        for command, rows in commands.items():
            ecus[address][command] = [
                {"raw": " ".join(line[i:i+2] for i in range(0,len(line),2)), "ms": int(ms)}
                for line, ms in rows
            ]
    return {"schema": "offline-replay-v1", "sources": ["Sanitized recorded diagnostic frames"], "ecus": ecus}
