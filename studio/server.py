"""LTX Video Enhancement Studio: REST API, Real-Time SSE Event Stream, and Static File Server."""
import asyncio, json, logging, os, shutil, sys, uuid
from pathlib import Path

from aiohttp import web

from common import ROOT, DIRS, STATIC, load_config, save_config, read_json, atomic_write_json, internal_token
from sysmon import snapshot
from comfy import ComfyProcess, ComfyClient
from engine import Engine
from jobs import JobManager
from settings import SCHEMA, BUILTIN_PRESETS, normalize
from video import probe_video, detect_scene_cuts, generate_timeline_thumbnails, target_resolution

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ltx.server")

comfy_proc = ComfyProcess()
comfy_client = ComfyClient()
engine = Engine(comfy_client)
job_mgr = JobManager(engine)


routes = web.RouteTableDef()


@routes.get("/")
async def handle_index(request):
    idx = STATIC / "index.html"
    if idx.exists():
        return web.FileResponse(idx)
    return web.Response(text="LTX Video Enhancement Studio backend running.", content_type="text/plain")


@routes.get("/api/status")
async def handle_status(request):
    snap = snapshot()
    h3_busy = await engine.check_h3_busy()
    snap["h3_busy"] = h3_busy
    snap["comfy"] = comfy_proc.status()
    snap["active_job"] = job_mgr.active_job is not None
    snap["queue_length"] = len(job_mgr.queue)
    return web.json_response(snap)


@routes.get("/api/installer/status")
async def handle_installer_status(request):
    p = DIRS["state"] / "install.json"
    doc = read_json(p, {"status": "uninstalled", "overall": {"pct": 0}})
    return web.json_response(doc)


@routes.get("/api/installer/events")
async def handle_installer_events(request):
    """Server-Sent Events (SSE) stream for real-time installer progress."""
    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
    await response.prepare(request)

    last_doc_str = ""
    p = DIRS["state"] / "install.json"

    try:
        while True:
            doc = read_json(p, {"status": "idle", "overall": {"pct": 0}})
            doc_str = json.dumps(doc)
            if doc_str != last_doc_str:
                last_doc_str = doc_str
                await response.write(f"data: {doc_str}\n\n".encode("utf-8"))
            await asyncio.sleep(0.5)
    except (asyncio.CancelledError, ConnectionResetError):
        pass

    return response


@routes.get("/api/jobs/events")
async def handle_jobs_events(request):
    """Server-Sent Events (SSE) stream for active job render progress."""
    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
    await response.prepare(request)

    queue = asyncio.Queue()

    def on_job_update(job):
        try:
            queue.put_nowait(json.dumps(job))
        except Exception:
            pass

    job_mgr.subscribe(on_job_update)
    try:
        while True:
            data = await queue.get()
            await response.write(f"data: {data}\n\n".encode("utf-8"))
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        job_mgr.unsubscribe(on_job_update)

    return response


@routes.post("/api/installer/token")
async def handle_save_token(request):
    data = await request.json()
    token = data.get("token", "").strip()
    f = DIRS["config"] / "hf_token"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(token)
    return web.json_response({"success": True})


@routes.post("/api/installer/start")
async def handle_installer_start(request):
    script = ROOT / "installer" / "install.py"
    if not script.exists():
        script = Path(__file__).resolve().parent.parent / "installer" / "install.py"
    if not script.exists():
        return web.json_response({"error": "Installer script not found"}, status=404)

    import subprocess
    subprocess.Popen([sys.executable, str(script), "--root", str(ROOT)], start_new_session=True)
    return web.json_response({"success": True, "message": "Installer launched in background."})


@routes.post("/api/upload")
async def handle_upload(request):
    reader = await request.multipart()
    field = await reader.next()
    if field.name != "video":
        return web.json_response({"error": "Expected field 'video'"}, status=400)

    filename = field.filename or "uploaded_video.mp4"
    file_id = uuid.uuid4().hex[:8]
    safe_name = f"{file_id}_{Path(filename).name}"
    dest_path = DIRS["inputs"] / safe_name

    size = 0
    with open(dest_path, "wb") as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)

    # Analyze metadata
    info = probe_video(str(dest_path))

    # Detect scene cuts
    cuts = detect_scene_cuts(str(dest_path))

    # Generate timeline thumbnails
    thumb_dir = DIRS["cache"] / "thumbnails" / file_id
    thumbs = generate_timeline_thumbnails(str(dest_path), str(thumb_dir), count=14)

    # Public URLs for thumbnails
    for th in thumbs:
        th["url"] = f"/thumbnails/{file_id}/{th['filename']}"

    # Default target resolution calculation
    geom = target_resolution(info["width"], info["height"], mode="refine", scale=1.5)

    return web.json_response({
        "success": True,
        "file_id": file_id,
        "filename": safe_name,
        "filepath": str(dest_path),
        "url": f"/inputs/{safe_name}",
        "size_bytes": size,
        "metadata": info,
        "scene_cuts": cuts,
        "thumbnails": thumbs,
        "geometry": geom
    })


@routes.post("/api/geometry")
async def handle_geometry_preview(request):
    data = await request.json()
    w = int(data.get("width", 1920))
    h = int(data.get("height", 1080))
    mode = data.get("mode", "refine")
    res_mode = data.get("resolution_mode", "scale")
    scale = float(data.get("scale", 1.5))
    long_edge = int(data.get("preset_long_edge", 1920))
    geom = target_resolution(w, h, mode, res_mode, scale, long_edge)
    return web.json_response(geom)


@routes.post("/api/jobs")
async def handle_create_job(request):
    data = await request.json()
    input_path = data.get("input_video_path")
    if not input_path or not os.path.exists(input_path):
        return web.json_response({"error": "Invalid or missing input_video_path"}, status=400)

    raw_settings = data.get("settings", {})
    clean_settings, warnings = normalize(raw_settings)

    job = await job_mgr.submit_job(input_path, clean_settings, name=data.get("name"))
    job["warnings"] = warnings
    is_queued = bool(job.get("queue_position", 0) > 0)
    return web.json_response({
        "success": True,
        "job": job,
        "is_queued": is_queued,
        "queue_position": job.get("queue_position", 0)
    })


@routes.get("/api/queue")
async def handle_get_queue(request):
    summary = await job_mgr.get_queue_summary()
    return web.json_response(summary)


@routes.get("/api/jobs")
async def handle_list_jobs(request):
    jobs = await job_mgr.list_jobs()
    return web.json_response(jobs)


@routes.get("/api/jobs/{id}")
async def handle_get_job(request):
    jid = request.match_info["id"]
    job = await job_mgr.get_job(jid)
    if not job:
        return web.json_response({"error": "Job not found"}, status=404)
    return web.json_response(job)


@routes.post("/api/jobs/{id}/cancel")
async def handle_cancel_job(request):
    jid = request.match_info["id"]
    ok = await job_mgr.cancel_job(jid)
    return web.json_response({"success": ok})


@routes.delete("/api/jobs/{id}")
async def handle_delete_job(request):
    jid = request.match_info["id"]
    ok = await job_mgr.delete_job(jid)
    return web.json_response({"success": ok})


@routes.post("/api/jobs/{id}/restart")
@routes.post("/api/jobs/{id}/retry")
async def handle_restart_job(request):
    jid = request.match_info["id"]
    try:
        new_job = await job_mgr.restart_job(jid)
        return web.json_response({"success": True, "job": new_job})
    except KeyError:
        return web.json_response({"error": "Job not found"}, status=404)


@routes.get("/api/settings/schema")
async def handle_schema(request):
    # Discover available model choices from ComfyUI object info or disk
    encoders = ["gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"]
    ggufs = ["LTX-2.5-Distilled-Q4_K_M.gguf"]
    vaes = ["ltx-2.5-video-vae-bf16.safetensors", "ltx-2.5-audio-vae-bf16.safetensors"]
    samplers = ["euler", "euler_ancestral", "dpmpp_2m", "res_multistep", "ddim", "uni_pc"]

    def _extract_combo(field):
        if not field:
            return []
        if isinstance(field, list):
            if len(field) > 1 and isinstance(field[1], dict) and "options" in field[1]:
                opts = field[1]["options"]
                if isinstance(opts, list):
                    return [str(x) for x in opts]
            if len(field) > 0 and isinstance(field[0], list):
                return [str(x) for x in field[0]]
            if all(isinstance(x, str) for x in field) and field[0] != "COMBO":
                return [str(x) for x in field]
        return []

    try:
        oi = await comfy_client.object_info()
        if "CLIPLoader" in oi:
            e = _extract_combo(oi["CLIPLoader"]["input"]["required"].get("clip_name"))
            if e:
                encoders = e
        if "UnetLoaderGGUF" in oi:
            g = _extract_combo(oi["UnetLoaderGGUF"]["input"]["required"].get("unet_name"))
            if g:
                ggufs = g
        if "VAELoader" in oi:
            v = _extract_combo(oi["VAELoader"]["input"]["required"].get("vae_name"))
            if v:
                vaes = v
        if "KSamplerSelect" in oi:
            s = _extract_combo(oi["KSamplerSelect"]["input"]["required"].get("sampler_name"))
            if s:
                samplers = s
    except Exception:
        pass

    return web.json_response({
        "schema": SCHEMA,
        "presets": BUILTIN_PRESETS,
        "discovered": {
            "encoders": encoders,
            "ggufs": ggufs,
            "vaes": vaes,
            "samplers": samplers
        }
    })


@routes.get("/api/presets")
async def handle_get_presets(request):
    all_p = dict(BUILTIN_PRESETS)
    # Load user presets from disk
    for f in DIRS["presets"].glob("*.json"):
        d = read_json(f)
        if d and "label" in d and "settings" in d:
            all_p[f.stem] = d
    return web.json_response(all_p)


@routes.post("/api/presets")
async def handle_save_preset(request):
    data = await request.json()
    name = data.get("name", "").strip()
    label = data.get("label", "").strip() or name
    raw_s = data.get("settings", {})
    if not name:
        return web.json_response({"error": "Preset name required"}, status=400)
    clean_s, _ = normalize(raw_s)
    p_path = DIRS["presets"] / f"{name}.json"
    atomic_write_json(p_path, {"label": label, "settings": clean_s})
    return web.json_response({"success": True, "name": name})


@routes.delete("/api/presets/{name}")
async def handle_delete_preset(request):
    name = request.match_info["name"]
    if name in BUILTIN_PRESETS:
        return web.json_response({"error": "Cannot delete built-in presets"}, status=400)
    p_path = DIRS["presets"] / f"{name}.json"
    if p_path.exists():
        p_path.unlink()
    return web.json_response({"success": True})


@routes.get("/api/models")
async def handle_models(request):
    manifest = read_json(ROOT / "installer" / "manifest.json") or read_json(Path(__file__).resolve().parent.parent / "installer" / "manifest.json")
    models = []
    for m in (manifest or {}).get("models", []):
        p = DIRS["models"] / m["dir"] / m["name"]
        exists = p.exists() and p.stat().st_size == m["size"]
        part = Path(str(p) + ".part")
        downloaded = p.stat().st_size if exists else (part.stat().st_size if part.exists() else 0)
        models.append({
            "id": m["id"],
            "label": m["label"],
            "name": m["name"],
            "dir": m["dir"],
            "size": m["size"],
            "downloaded": downloaded,
            "ready": exists,
            "group": m["group"],
            "required": m["required"]
        })
    return web.json_response({"models": models})


@routes.post("/api/internal/comfy/start")
async def handle_internal_start(request):
    tok = request.headers.get("X-Internal-Token")
    if tok != internal_token():
        return web.json_response({"error": "Unauthorized"}, status=401)
    ok = comfy_proc.start()
    return web.json_response({"success": ok, "status": comfy_proc.status()})


@routes.post("/api/internal/comfy/restart")
async def handle_internal_restart(request):
    tok = request.headers.get("X-Internal-Token")
    if tok != internal_token():
        return web.json_response({"error": "Unauthorized"}, status=401)
    ok = comfy_proc.restart()
    return web.json_response({"success": ok, "status": comfy_proc.status()})


async def on_startup(app):
    job_mgr.start()
    # If models are present, start ComfyUI worker automatically
    dit = DIRS["models"] / "diffusion_models" / "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
    if dit.exists() and dit.stat().st_size > 1000:
        comfy_proc.start()


@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


def make_app():
    app = web.Application(client_max_size=1024 * 1024 * 1024, middlewares=[cors_middleware])
    app.on_startup.append(on_startup)

    app.add_routes(routes)

    # Static mounts
    app.router.add_static("/static", str(STATIC))
    app.router.add_static("/inputs", str(DIRS["inputs"]))
    app.router.add_static("/outputs", str(DIRS["outputs"]))
    (DIRS["cache"] / "thumbnails").mkdir(parents=True, exist_ok=True)
    app.router.add_static("/thumbnails", str(DIRS["cache"] / "thumbnails"))

    return app


if __name__ == "__main__":
    cfg = load_config()
    host = cfg.get("host", "0.0.0.0")
    port = int(cfg.get("port", 7860))
    app = make_app()
    web.run_app(app, host=host, port=port)
