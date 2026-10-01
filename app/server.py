import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from aiohttp import web

from gpu_manager import GPUManager
from pipeline import LTXPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ltx.server")

DEFAULT_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_DIR = os.environ.get("LTX_BASE_DIR", DEFAULT_BASE)
INPUTS_DIR = os.path.join(BASE_DIR, "inputs")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
STATIC_DIR = os.path.join(BASE_DIR, "app", "static")

gpu_manager = GPUManager(h3_url="http://127.0.0.1:8188")
pipeline = LTXPipeline(base_dir=BASE_DIR)

gpu_manager.set_job_runner(pipeline.execute_job)

routes = web.RouteTableDef()

@routes.get("/")
async def handle_index(request):
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return web.FileResponse(index_file)
    return web.Response(text="LTX 2.5 Video Enhancement Studio", content_type="text/plain")

@routes.get("/api/gpu_status")
async def handle_gpu_status(request):
    h3_busy = await gpu_manager.check_h3_busy()
    gpu_busy = await gpu_manager.check_gpu_busy()
    available = not (h3_busy or gpu_busy)
    
    # Query nvidia-smi stats
    vram_used = 0
    vram_total = 32768
    gpu_util = 0
    try:
        import subprocess
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            encoding="utf-8"
        )
        line = output.strip().split("\n")[0]
        gpu_util, vram_used, vram_total = [float(x.strip()) for x in line.split(",")]
    except Exception:
        pass

    # Check transformer download progress
    transformer_path = os.path.join(BASE_DIR, "models", "diffusion_models", "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors")
    transformer_tmp = transformer_path + ".tmp"
    model_ready = os.path.exists(transformer_path)
    model_download_gb = 0
    model_download_pct = 100.0
    if not model_ready and os.path.exists(transformer_tmp):
        downloaded = os.path.getsize(transformer_tmp)
        model_download_gb = round(downloaded / 1e9, 2)
        model_download_pct = round((downloaded / 21503348736) * 100, 1)

    return web.json_response({
        "h3_busy": h3_busy,
        "external_gpu_busy": gpu_busy,
        "gpu_available": available,
        "gpu_utilization_pct": gpu_util,
        "vram_used_mb": vram_used,
        "vram_total_mb": vram_total,
        "active_job": gpu_manager.active_job is not None,
        "queue_length": len(gpu_manager.queue),
        "model_ready": model_ready,
        "model_download_gb": model_download_gb,
        "model_download_pct": model_download_pct,
        "stats": pipeline.stats.get_summary()
    })

@routes.get("/api/stats")
async def handle_stats(request):
    return web.json_response(pipeline.stats.get_summary())

@routes.post("/api/upload")
async def handle_upload(request):
    reader = await request.multipart()
    field = await reader.next()
    if field.name != 'video':
        return web.json_response({"error": "Expected field 'video'"}, status=400)
    
    filename = field.filename or "uploaded_video.mp4"
    file_id = uuid.uuid4().hex[:8]
    safe_name = f"{file_id}_{os.path.basename(filename)}"
    dest_path = os.path.join(INPUTS_DIR, safe_name)
    
    size = 0
    with open(dest_path, 'wb') as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)
            
    info = pipeline.probe_video(dest_path)
    est_dur = pipeline.stats.estimate_job_duration(info.get("duration", 5.0), "FullHD")

    return web.json_response({
        "success": True,
        "file_id": file_id,
        "filename": safe_name,
        "filepath": dest_path,
        "url": f"/inputs/{safe_name}",
        "size_bytes": size,
        "metadata": info,
        "estimated_duration_seconds": est_dur,
        "formatted_eta": pipeline.stats.format_eta(est_dur)
    })

@routes.post("/api/jobs")
async def handle_create_job(request):
    data = await request.json()
    input_path = data.get("input_video_path")
    if not input_path or not os.path.exists(input_path):
        return web.json_response({"error": "Invalid or missing input_video_path"}, status=400)
    
    mode = data.get("mode", "refine") # "refine" or "restore"
    resolution = data.get("resolution", "FullHD")
    lora_strength = float(data.get("lora_strength", 1.0))
    seed = int(data.get("seed", 42))
    user_prompt = data.get("prompt", "")

    # Calculate initial estimate from video duration
    info = pipeline.probe_video(input_path)
    est_duration = pipeline.stats.estimate_job_duration(info.get("duration", 5.0), resolution)

    job_data = {
        "id": f"ltx_{uuid.uuid4().hex[:8]}",
        "input_video_path": input_path,
        "input_video_url": f"/inputs/{os.path.basename(input_path)}",
        "mode": mode,
        "resolution": resolution,
        "lora_strength": lora_strength,
        "seed": seed,
        "prompt": user_prompt,
        "video_info": info,
        "estimated_total_seconds": est_duration,
        "estimated_remaining_seconds": est_duration,
        "eta_text": pipeline.stats.format_eta(est_duration)
    }

    job = await gpu_manager.submit_job(job_data)
    return web.json_response({"success": True, "job": job})

@routes.get("/api/jobs")
async def handle_get_jobs(request):
    all_jobs = await gpu_manager.get_all_jobs()
    return web.json_response(all_jobs)

@routes.get("/api/jobs/{id}")
async def handle_get_job(request):
    job_id = request.match_info["id"]
    job = await gpu_manager.get_job(job_id)
    if not job:
        return web.json_response({"error": "Job not found"}, status=404)
    return web.json_response(job)

@routes.post("/api/jobs/{id}/cancel")
async def handle_cancel_job(request):
    job_id = request.match_info["id"]
    success = await gpu_manager.cancel_job(job_id)
    return web.json_response({"success": success})

@routes.delete("/api/jobs/{id}")
async def handle_delete_job(request):
    job_id = request.match_info["id"]
    success = await gpu_manager.delete_job(job_id)
    return web.json_response({"success": success})


async def on_startup(app):
    gpu_manager.start_worker()

def make_app():
    app = web.Application(client_max_size=1024*1024*1024) # 1GB max upload
    app.on_startup.append(on_startup)
    app.add_routes(routes)
    app.router.add_static("/static", STATIC_DIR)
    app.router.add_static("/outputs", OUTPUTS_DIR)
    app.router.add_static("/inputs", INPUTS_DIR)
    return app

if __name__ == "__main__":
    app = make_app()
    web.run_app(app, host="0.0.0.0", port=7860)
