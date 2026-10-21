"""Exercise real fadtk CLAP inference on synthetic fixtures, not quality claims."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import soundfile as sf
from backend.config import DATA, ROOT, settings

if __name__ == "__main__":
    ss=[]
    for i in range(4):
        path=DATA/'audio'/f'fad-smoke-{i}.wav'
        sr=24000
        t=np.arange(sr*2)/sr
        sf.write(path,np.sin(2*np.pi*(220+i*55)*t)*.1,sr)
        ss.append({"id":f"fixture-{i}","path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"audio_type":"instrumental","tags":"synthetic"})
    options=settings()
    payload={"metric":"fad","sample":ss[0],"samples":ss[:2],"references":ss[2:],"options":options}
    p=subprocess.run([str(ROOT/'.venv-fad/Scripts/python.exe'),'-m','backend.worker'],input=json.dumps(payload),capture_output=True,
                     encoding='utf-8',text=True,cwd=ROOT,env={**os.environ,"PYTHONIOENCODING":"utf-8"},timeout=1800)
    try:result=json.loads(p.stdout)
    except ValueError:result={"status":"failed","reason":p.stderr[-4000:]}
    if result["status"]=="success":
        payload["options"]["offline"]=True
        from backend.metrics import fingerprint
        for s in ss:
            cache=DATA/'cache'/('fad-'+fingerprint({**result['value']['protocol'],'sha256':s['sha256']})+'.npy')
            cache.unlink(missing_ok=True)  # Only these four synthetic fixtures.
        # Exercise full model loading + embedding inference offline, not only stats.
        p2=subprocess.run([str(ROOT/'.venv-fad/Scripts/python.exe'),'-m','backend.worker'],input=json.dumps(payload),capture_output=True,
                          encoding='utf-8',text=True,cwd=ROOT,env={**os.environ,"PYTHONIOENCODING":"utf-8"},timeout=1800)
        try:result["offline_repeat"]=json.loads(p2.stdout)
        except ValueError:result["offline_repeat"]={"status":"failed","reason":p2.stderr[-4000:]}
    (ROOT/'docs/fad-smoke.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
