import os
import json
import logging
import time
from typing import Dict, Any

logger = logging.getLogger("ltx.stats")

DEFAULT_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_DIR = os.environ.get("LTX_BASE_DIR", DEFAULT_BASE)
STATS_FILE = os.path.join(BASE_DIR, "stats.json")

DEFAULT_STATS = {
    "total_renders": 0,
    "total_video_seconds_rendered": 0.0,
    "total_render_seconds": 0.0,
    "history": [], # list of {id, duration, resolution, mode, elapsed, sec_per_sec, timestamp}
    "rates": {
        "FullHD": 5.0, # default baseline: 5s render per 1s video on RTX 5090
        "4K": 14.0
    }
}

class StatsManager:
    def __init__(self, stats_path: str = STATS_FILE):
        self.stats_path = stats_path
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.stats_path):
            try:
                with open(self.stats_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load stats.json: {e}")
        return json.loads(json.dumps(DEFAULT_STATS))

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
            with open(self.stats_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save stats.json: {e}")

    def record_job_completion(self, job_id: str, video_duration: float, resolution: str, mode: str, elapsed_seconds: float):
        if video_duration <= 0 or elapsed_seconds <= 0:
            return

        sec_per_sec = round(elapsed_seconds / video_duration, 2)
        record = {
            "job_id": job_id,
            "video_duration": round(video_duration, 2),
            "resolution": resolution,
            "mode": mode,
            "elapsed_seconds": round(elapsed_seconds, 1),
            "seconds_per_video_second": sec_per_sec,
            "timestamp": time.time()
        }

        self.data["total_renders"] += 1
        self.data["total_video_seconds_rendered"] = round(self.data["total_video_seconds_rendered"] + video_duration, 2)
        self.data["total_render_seconds"] = round(self.data["total_render_seconds"] + elapsed_seconds, 1)
        self.data["history"].append(record)

        # Keep last 50 historical entries
        if len(self.data["history"]) > 50:
            self.data["history"] = self.data["history"][-50:]

        # Recalculate average rate for resolution
        matching = [h for h in self.data["history"] if h["resolution"] == resolution]
        if matching:
            avg_rate = sum(h["seconds_per_video_second"] for h in matching) / len(matching)
            self.data["rates"][resolution] = round(avg_rate, 2)

        self._save()
        logger.info(f"Updated stats after job {job_id}: rate for {resolution} is now {self.data['rates'].get(resolution)}s/s")

    def estimate_job_duration(self, video_duration: float, resolution: str = "FullHD") -> float:
        rate = self.data["rates"].get(resolution, 5.0)
        # Baseline model loading / startup overhead ~15s + sampling time
        overhead = 15.0
        return max(20.0, round((video_duration * rate) + overhead, 1))

    def format_eta(self, remaining_seconds: float) -> str:
        rem = max(0, int(remaining_seconds))
        if rem <= 0:
            return "Almost done..."
        mins = rem // 60
        secs = rem % 60
        if mins > 0:
            return f"~{mins}m {secs}s remaining"
        return f"~{secs}s remaining"

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_renders": self.data["total_renders"],
            "total_video_seconds_rendered": self.data["total_video_seconds_rendered"],
            "rates": self.data["rates"],
            "recent_runs": self.data["history"][-5:]
        }
