"""GPU / RAM / disk monitoring."""
import shutil, subprocess, time
from collections import deque

import psutil

from common import ROOT, ram_limits


def gpu_info():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit,driver_version",
             "--format=csv,noheader,nounits"], text=True, timeout=5).strip().splitlines()[0]
        n, util, used, total, temp, pw, pl, drv = [x.strip() for x in out.split(",")]
        f = lambda v: float(v) if v.replace(".", "", 1).isdigit() else None
        info = {"name": n, "util": f(util), "vram_used_mb": f(used), "vram_total_mb": f(total), "temp_c": f(temp),
                "power_w": f(pw), "power_limit_w": f(pl), "driver": drv}
    except Exception:
        return {"available": False}
    info["available"] = True
    procs = []
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,used_memory,process_name", "--format=csv,noheader,nounits"], text=True, timeout=5)
        for l in out.strip().splitlines():
            p = [x.strip() for x in l.split(",")]
            if len(p) >= 3:
                procs.append({"pid": int(p[0]), "mb": float(p[1]), "name": p[2].split("/")[-1]})
    except Exception:
        pass
    info["procs"] = procs
    return info


def snapshot():
    total, avail = ram_limits()
    du = shutil.disk_usage(ROOT if ROOT.exists() else "/")
    return {"t": time.time(), "gpu": gpu_info(),
            "ram": {"total_gb": round(total, 1), "available_gb": round(avail, 1), "used_pct": round(100 - avail * 100 / total, 1) if total else 0},
            "cpu_pct": psutil.cpu_percent(interval=None),
            "disk": {"free_gb": round(du.free / 1e9, 1), "total_gb": round(du.total / 1e9, 1)}}


class Monitor:
    def __init__(self, n=180):
        self.hist = deque(maxlen=n)
        self.last = None

    def sample(self):
        s = snapshot()
        self.last = s
        g = s["gpu"]
        self.hist.append({"t": s["t"], "util": g.get("util"), "vram": g.get("vram_used_mb"), "ram": s["ram"]["used_pct"]})
        return s


def free_vram_mb():
    g = gpu_info()
    if not g.get("available"):
        return None
    return g["vram_total_mb"] - g["vram_used_mb"]
