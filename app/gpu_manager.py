import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any, Callable
import aiohttp

logger = logging.getLogger("ltx.gpu_manager")

DEFAULT_BASE = "/root/ltx-enhancer" if os.path.exists("/root/ltx-enhancer") else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_DIR = os.environ.get("LTX_BASE_DIR", DEFAULT_BASE)
JOBS_DB_PATH = os.path.join(BASE_DIR, "jobs.json")

class GPUManager:
    """
    Orchestrates FIFO queueing and GPU mutual exclusivity.
    Never runs LTX inference while Minimax H3 or other production is using the GPU.
    Persists job history so completed generations are never lost.
    """
    def __init__(self, h3_url: str = "http://127.0.0.1:8188", vram_threshold_mb: int = 14000):
        self.h3_url = h3_url.rstrip("/")
        self.vram_threshold_mb = vram_threshold_mb
        self.queue: List[Dict[str, Any]] = []
        self.active_job: Optional[Dict[str, Any]] = None
        self.completed_jobs: Dict[str, Dict[str, Any]] = self._load_completed_jobs()
        self.lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None
        self._on_job_start: Optional[Callable] = None

    def _load_completed_jobs(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(JOBS_DB_PATH):
            try:
                with open(JOBS_DB_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load jobs.json: {e}")
        return {}

    def _save_completed_jobs(self):
        try:
            os.makedirs(os.path.dirname(JOBS_DB_PATH), exist_ok=True)
            with open(JOBS_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(self.completed_jobs, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save jobs.json: {e}")

    def set_job_runner(self, runner_callback: Callable):
        self._on_job_start = runner_callback

    def start_worker(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._queue_worker_loop())

    async def check_h3_busy(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.h3_url}/queue", timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        running = data.get("queue_running", [])
                        pending = data.get("queue_pending", [])
                        if len(running) > 0 or len(pending) > 0:
                            return True
        except Exception:
            pass
        return False

    async def check_gpu_busy(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            line = stdout.decode().strip().split("\n")[0]
            mem_used_str, util_str = line.split(",")
            mem_used = float(mem_used_str.strip())
            util = float(util_str.strip())

            # If VRAM > 14 GB and no active LTX job, another production model is running
            if self.active_job is None and mem_used > self.vram_threshold_mb:
                return True
            if self.active_job is None and util > 40:
                return True
        except Exception as e:
            logger.warning(f"Failed to inspect GPU via nvidia-smi: {e}")
        return False

    async def is_gpu_available(self) -> bool:
        if await self.check_h3_busy():
            return False
        if await self.check_gpu_busy():
            return False
        return True

    async def submit_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        async with self.lock:
            job["status"] = "QUEUED"
            job["created_at"] = time.time()
            job["started_at"] = None
            job["completed_at"] = None
            job["elapsed_seconds"] = 0
            job["progress"] = 0
            job["stage"] = "In Queue"
            job["error"] = None
            job["queue_position"] = len(self.queue) + 1
            self.queue.append(job)
            self.start_worker()
            return job

    async def cancel_job(self, job_id: str) -> bool:
        async with self.lock:
            for i, j in enumerate(self.queue):
                if j["id"] == job_id:
                    self.queue.pop(i)
                    j["status"] = "CANCELLED"
                    j["stage"] = "Cancelled by user"
                    j["completed_at"] = time.time()
                    self.completed_jobs[job_id] = j
                    self._save_completed_jobs()
                    self._update_queue_positions()
                    return True
            if self.active_job and self.active_job["id"] == job_id:
                self.active_job["status"] = "CANCELLED"
                self.active_job["stage"] = "Cancelling..."
                return True
        return False

    async def delete_job(self, job_id: str) -> bool:
        async with self.lock:
            if job_id in self.completed_jobs:
                job = self.completed_jobs.pop(job_id)
                out_path = job.get("output_video_path")
                if out_path and os.path.exists(out_path):
                    try:
                        os.remove(out_path)
                    except Exception as e:
                        logger.warning(f"Could not remove output file {out_path}: {e}")
                self._save_completed_jobs()
                return True
        return False

    def _update_queue_positions(self):
        for idx, job in enumerate(self.queue):
            job["queue_position"] = idx + 1

    async def get_all_jobs(self) -> Dict:
        async with self.lock:
            self._update_queue_positions()
            # Sort completed jobs by completed_at desc
            completed_list = sorted(
                list(self.completed_jobs.values()),
                key=lambda x: x.get("completed_at") or 0,
                reverse=True
            )
            return {
                "active": self.active_job,
                "queued": list(self.queue),
                "completed": completed_list
            }

    async def get_job(self, job_id: str) -> Optional[Dict]:
        async with self.lock:
            if self.active_job and self.active_job["id"] == job_id:
                return self.active_job
            for j in self.queue:
                if j["id"] == job_id:
                    return j
            return self.completed_jobs.get(job_id)

    async def _queue_worker_loop(self):
        logger.info("Starting LTX GPU Queue Worker loop...")
        while True:
            job_to_run = None
            async with self.lock:
                if self.queue and self.active_job is None:
                    job_to_run = self.queue[0]

            if not job_to_run:
                await asyncio.sleep(2)
                continue

            gpu_ok = await self.is_gpu_available()
            if not gpu_ok:
                async with self.lock:
                    job_to_run["status"] = "WAITING_FOR_GPU"
                    job_to_run["stage"] = "Waiting for GPU (H3 / Production Busy)"
                await asyncio.sleep(3)
                continue

            async with self.lock:
                if self.queue and self.queue[0]["id"] == job_to_run["id"]:
                    self.active_job = self.queue.pop(0)
                    self._update_queue_positions()
                    self.active_job["status"] = "RUNNING"
                    self.active_job["started_at"] = time.time()
                    self.active_job["stage"] = "Starting enhancement pipeline..."
                    self.active_job["progress"] = 5

            if self._on_job_start:
                try:
                    await self._on_job_start(self.active_job)
                except Exception as e:
                    logger.error(f"Job {self.active_job['id']} failed: {e}", exc_info=True)
                    self.active_job["status"] = "FAILED"
                    self.active_job["error"] = str(e)
                    self.active_job["stage"] = f"Failed: {e}"

            async with self.lock:
                if self.active_job:
                    if self.active_job["status"] not in ("FAILED", "CANCELLED"):
                        self.active_job["status"] = "COMPLETED"
                        self.active_job["stage"] = "Completed successfully"
                        self.active_job["progress"] = 100
                    self.active_job["completed_at"] = time.time()
                    self.completed_jobs[self.active_job["id"]] = self.active_job
                    self._save_completed_jobs()
                    self.active_job = None

            await asyncio.sleep(1)
