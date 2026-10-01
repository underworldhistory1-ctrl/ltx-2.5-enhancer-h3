import asyncio
import glob
import json
import logging
import os
import shutil
import subprocess
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
import aiohttp

from workflow_builder import build_v2v_workflow
from stats_manager import StatsManager

logger = logging.getLogger("ltx.pipeline")

BASE_URL = "http://127.0.0.1:8189"
WS_URL = "http://127.0.0.1:8189/ws"

DEFAULT_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_DIR = os.environ.get("LTX_BASE_DIR", DEFAULT_BASE)
TRANSFORMER_PATH = os.path.join(BASE_DIR, "models", "diffusion_models", "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors")
TRANSFORMER_TMP_PATH = TRANSFORMER_PATH + ".tmp"
TOTAL_TRANSFORMER_BYTES = 21503348736

class LTXPipeline:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or BASE_DIR
        self.base_dir = base_dir
        self.inputs_dir = os.path.join(base_dir, "inputs")
        self.outputs_dir = os.path.join(base_dir, "outputs")
        self.temp_dir = os.path.join(base_dir, "temp")
        self.comfy_input_dir = os.path.join(base_dir, "comfy_backend", "input")
        self.comfy_output_dir = os.path.join(base_dir, "comfy_backend", "output")
        self.stats = StatsManager()

        os.makedirs(self.inputs_dir, exist_ok=True)
        os.makedirs(self.outputs_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.comfy_input_dir, exist_ok=True)
        os.makedirs(self.comfy_output_dir, exist_ok=True)

    def probe_video(self, video_path: str) -> Dict[str, Any]:
        """Probes video metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration",
            "-of", "json",
            video_path
        ]
        width, height, fps, duration, frames = 1920, 1080, 24.0, 0.0, 0
        try:
            out = subprocess.check_output(cmd, encoding="utf-8")
            data = json.loads(out)
            streams = data.get("streams", [])
            if streams:
                st = streams[0]
                width = int(st.get("width", 1920))
                height = int(st.get("height", 1080))
                if "/" in st.get("r_frame_rate", "24/1"):
                    num, den = st["r_frame_rate"].split("/")
                    fps = round(float(num) / float(den), 2)
                else:
                    fps = float(st.get("r_frame_rate", 24.0))
                duration = float(st.get("duration", 0.0))
                frames = int(st.get("nb_frames", 0))
        except Exception as e:
            logger.warning(f"ffprobe failed for {video_path}: {e}")

        # Check for audio stream
        has_audio = False
        try:
            cmd_a = [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type",
                "-of", "json",
                video_path
            ]
            out_a = subprocess.check_output(cmd_a, encoding="utf-8")
            data_a = json.loads(out_a)
            has_audio = len(data_a.get("streams", [])) > 0
        except Exception:
            pass

        if duration == 0.0 and frames > 0 and fps > 0:
            duration = round(frames / fps, 2)

        return {
            "width": width,
            "height": height,
            "fps": fps,
            "duration": duration,
            "frames": frames,
            "has_audio": has_audio
        }

    def extract_audio(self, video_path: str, output_audio_path: str) -> bool:
        """Losslessly extracts original audio stream."""
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "copy",
            output_audio_path
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 100
        except Exception:
            # Fallback re-encode audio if stream copy fails
            try:
                cmd_fallback = [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn", "-acodec", "aac", "-b:a", "192k",
                    output_audio_path
                ]
                subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 100
            except Exception as e:
                logger.error(f"Audio extraction failed: {e}")
                return False

    def mux_video_audio(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """Muxes original audio losslessly back into enhanced video."""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logger.error(f"Failed to mux audio: {e}")
            shutil.copy2(video_path, output_path)
            return False

    async def execute_job(self, job: Dict[str, Any]):
        job_id = job["id"]
        input_path = job["input_video_path"]
        mode = job.get("mode", "refine")
        resolution = job.get("resolution", "FullHD")
        lora_strength = float(job.get("lora_strength", 1.0))
        seed = int(job.get("seed", 42))

        # Check if transformer model download is complete
        while not os.path.exists(TRANSFORMER_PATH):
            downloaded = 0
            if os.path.exists(TRANSFORMER_TMP_PATH):
                downloaded = os.path.getsize(TRANSFORMER_TMP_PATH)
            pct = round((downloaded / TOTAL_TRANSFORMER_BYTES) * 100, 1)
            gb = round(downloaded / 1e9, 2)
            job["stage"] = f"Waiting for LTX 2.5 Transformer weights: {pct}% ({gb} / 21.5 GB)..."
            job["progress"] = max(5, int(pct * 0.1))
            job["eta_text"] = "Waiting for model download..."
            logger.info(f"Job {job_id} waiting for model download: {pct}%")
            await asyncio.sleep(5)

        logger.info(f"Starting pipeline execution for job {job_id} (mode={mode}, res={resolution})")
        
        # 1. Probe & extract audio
        job["stage"] = "Analyzing input video & extracting audio..."
        job["progress"] = 10
        info = self.probe_video(input_path)
        job["video_info"] = info
        v_duration = info.get("duration", 5.0)

        # Calculate initial adaptive ETA
        est_duration = self.stats.estimate_job_duration(v_duration, resolution)
        job["estimated_total_seconds"] = est_duration
        job["estimated_remaining_seconds"] = est_duration
        job["eta_text"] = self.stats.format_eta(est_duration)

        # LTX requires 8n+1 source frames for aligned temporal windows.
        source_frames = info["frames"] or max(1, round(info["duration"] * info["fps"]))
        pad_frames = (1 - source_frames) % 8
        if pad_frames:
            job["stage"] = f"Preparing {pad_frames} alignment frames..."
            basename = f"{job_id}_aligned.mp4"
            comfy_input_file = os.path.join(self.comfy_input_dir, basename)
            target_duration = (source_frames + pad_frames) / info["fps"]
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error", "-i", input_path,
                "-vf", f"tpad=stop_mode=clone:stop={pad_frames}",
                "-af", "apad", "-t", str(target_duration),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", comfy_input_file
            ], check=True)
            workflow_frames = source_frames + pad_frames
        else:
            basename = os.path.basename(input_path)
            comfy_input_file = os.path.join(self.comfy_input_dir, basename)
            if not os.path.exists(comfy_input_file):
                shutil.copy2(input_path, comfy_input_file)
            workflow_frames = source_frames

        audio_file = os.path.join(self.temp_dir, f"{job_id}_original_audio.m4a")
        has_audio = False
        if info["has_audio"]:
            has_audio = self.extract_audio(input_path, audio_file)

        # 2. Build ComfyUI workflow
        prefix = f"ltx_{job_id}"
        user_prompt = job.get("prompt")
        kwargs = {
            "input_video_filename": basename,
            "output_filename_prefix": prefix,
            "mode": mode,
            "resolution_preset": resolution,
            "lora_strength": lora_strength,
            "seed": seed,
            "frame_count": workflow_frames
        }
        if user_prompt:
            kwargs["positive_prompt"] = user_prompt

        prompt = build_v2v_workflow(**kwargs)

        job["stage"] = "Submitting graph to isolated LTX ComfyUI backend..."
        job["progress"] = 18

        # 3. Post prompt to ComfyUI
        loop = asyncio.get_running_loop()
        client_id = f"ltx_client_{job_id}"
        payload = json.dumps({"prompt": prompt, "client_id": client_id}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        try:
            res_raw = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=12).read())
            res_data = json.loads(res_raw.decode())
            prompt_id = res_data.get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"ComfyUI prompt submission returned no prompt_id: {res_data}")
            job["prompt_id"] = prompt_id
            logger.info(f"Job {job_id} submitted to ComfyUI with prompt_id: {prompt_id}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            raise RuntimeError(f"ComfyUI validation error: {err_body[:300]}")
        except Exception as e:
            raise RuntimeError(f"Failed to submit prompt to ComfyUI worker: {e}")

        # 4. Monitor execution via WebSocket & History
        start_time = time.time()
        job["stage"] = "Initializing LTX 2.5 pipeline on RTX 5090..."
        job["progress"] = 22

        ws_task = asyncio.create_task(self._monitor_websocket(client_id, prompt_id, job, est_duration, start_time))
        
        # Wait for prompt to appear in history
        history_entry = None
        prompt_seen_in_queue = False
        missing_after_seen = 0
        while True:
            if job.get("status") == "CANCELLED":
                try:
                    interrupt_req = urllib.request.Request(f"{BASE_URL}/interrupt", data=b"{}")
                    await loop.run_in_executor(None, lambda: urllib.request.urlopen(interrupt_req, timeout=2))
                except Exception:
                    pass
                ws_task.cancel()
                raise RuntimeError("Job cancelled by user")

            # Check if ComfyUI finished this prompt
            try:
                hist_req = urllib.request.Request(f"{BASE_URL}/history/{prompt_id}")
                hist_raw = await loop.run_in_executor(None, lambda: urllib.request.urlopen(hist_req, timeout=3).read())
                hist_data = json.loads(hist_raw.decode())
                if prompt_id in hist_data:
                    history_entry = hist_data[prompt_id]
                    logger.info(f"ComfyUI prompt {prompt_id} completed!")
                    break
            except Exception:
                pass

            # A restarted ComfyUI worker loses its in-memory queue and history.
            # Surface that failure instead of leaving the job at a false 5-second ETA.
            try:
                queue_req = urllib.request.Request(f"{BASE_URL}/queue")
                queue_raw = await loop.run_in_executor(None, lambda: urllib.request.urlopen(queue_req, timeout=3).read())
                queue_data = json.loads(queue_raw.decode())
                queued_ids = {item[1] for key in ("queue_running", "queue_pending") for item in queue_data.get(key, []) if len(item) > 1}
                if prompt_id in queued_ids:
                    prompt_seen_in_queue = True
                    missing_after_seen = 0
                elif prompt_seen_in_queue:
                    missing_after_seen += 1
                    if missing_after_seen >= 3:
                        raise RuntimeError("LTX worker lost the render after a restart; check server RAM")
            except RuntimeError:
                raise
            except Exception:
                pass

            elapsed = time.time() - start_time
            if elapsed < est_duration:
                rem = est_duration - elapsed
                job["estimated_remaining_seconds"] = round(rem, 1)
                job["eta_text"] = self.stats.format_eta(rem)
            else:
                job["estimated_remaining_seconds"] = None
                job["eta_text"] = "Still processing; timing estimate unavailable"

            await asyncio.sleep(2)

        ws_task.cancel()

        # 5. Check outputs from history
        job["stage"] = "Collecting rendered output and muxing audio..."
        job["progress"] = 94
        job["eta_text"] = "Finalizing video..."

        # Look for output file matching prefix
        output_candidates = glob.glob(os.path.join(self.comfy_output_dir, f"{prefix}*.mp4"))
        if not output_candidates:
            output_candidates = glob.glob(os.path.join(self.comfy_output_dir, "**", f"{prefix}*.mp4"), recursive=True)

        if not output_candidates:
            # Check history outputs
            outputs = history_entry.get("outputs", {})
            for node_id, node_out in outputs.items():
                if "videos" in node_out:
                    for v in node_out["videos"]:
                        fn = v.get("filename")
                        sub = v.get("subfolder", "")
                        cand = os.path.join(self.comfy_output_dir, sub, fn)
                        if os.path.exists(cand):
                            output_candidates.append(cand)

        if not output_candidates:
            raise RuntimeError(f"Enhanced video file not found for job {job_id}")

        raw_output_video = output_candidates[0]
        final_filename = f"enhanced_{job_id}_{basename}"
        final_output_path = os.path.join(self.outputs_dir, final_filename)

        # Remove alignment padding and honor Original resolution in the delivered file.
        if pad_frames or resolution.lower() == "original":
            vf = f"trim=end_frame={source_frames},setpts=PTS-STARTPTS"
            if resolution.lower() == "original":
                vf += f",scale={info['width']}:{info['height']}:flags=lanczos"
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", raw_output_video]
            if has_audio and os.path.exists(audio_file):
                cmd += ["-i", audio_file, "-map", "0:v:0", "-map", "1:a:0"]
            else:
                cmd += ["-map", "0:v:0", "-an"]
            cmd += ["-vf", vf, "-frames:v", str(source_frames),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17"]
            if has_audio and os.path.exists(audio_file):
                cmd += ["-c:a", "aac", "-b:a", "192k"]
            cmd += ["-t", str(v_duration), "-shortest", final_output_path]
            subprocess.run(cmd, check=True)
        elif has_audio and os.path.exists(audio_file):
            self.mux_video_audio(raw_output_video, audio_file, final_output_path)
        else:
            shutil.copy2(raw_output_video, final_output_path)

        # 6. Record completion statistics & adaptive learning
        total_elapsed = round(time.time() - start_time, 1)
        self.stats.record_job_completion(
            job_id=job_id,
            video_duration=v_duration,
            resolution=resolution,
            mode=mode,
            elapsed_seconds=total_elapsed
        )

        job["output_video_path"] = final_output_path
        job["output_video_url"] = f"/outputs/{final_filename}"
        job["elapsed_seconds"] = total_elapsed
        job["eta_text"] = f"Finished in {int(total_elapsed)}s"
        job["progress"] = 100
        job["stage"] = "Enhancement complete!"
        logger.info(f"Job {job_id} successfully finished in {total_elapsed}s!")

    async def _monitor_websocket(self, client_id: str, prompt_id: str, job: Dict[str, Any], est_duration: float, start_time: float):
        """Streams live node and step progress directly from ComfyUI WebSocket."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(f"{WS_URL}?clientId={client_id}") as ws:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            mtype = data.get("type")
                            mdata = data.get("data", {})

                            if mdata.get("prompt_id") and mdata.get("prompt_id") != prompt_id:
                                continue

                            if mtype == "executing":
                                node = mdata.get("node")
                                if node in ["audio_vae_loader", "video_vae_loader", "unet_loader", "clip_loader", "ic_lora_loader"]:
                                    job["stage"] = "Loading LTX 2.5 neural weights into RTX 5090..."
                                    job["progress"] = 25
                                elif node in ["load_video", "video_components", "scale_guide", "tiling_sizes", "empty_latent"]:
                                    job["stage"] = "Decomposing frames & setting up Tiled Latents..."
                                    job["progress"] = 38
                                elif node == "tiled_fusion_sampler":
                                    job["stage"] = "Denoising with LTX 2.5 Tiled Fusion..."
                                    job["progress"] = 50
                                elif node == "tiled_decode":
                                    job["stage"] = "Decoding latents with Video VAE..."
                                    job["progress"] = 88
                                elif node in ["create_video", "save_video"]:
                                    job["stage"] = "Encoding final high-resolution video..."
                                    job["progress"] = 93

                            elif mtype == "progress":
                                val = mdata.get("value", 0)
                                max_val = mdata.get("max", 8)
                                job["step_current"] = val
                                job["step_max"] = max_val
                                job["stage"] = f"Sampling & Denoising: step {val} of {max_val}..."
                                pct = 50 + int((val / max_val) * 35)
                                job["progress"] = pct
                                
                                # Dynamic step-based remaining time calculation
                                if val > 0:
                                    elapsed = time.time() - start_time
                                    step_rate = elapsed / val
                                    rem_steps = max(0, max_val - val)
                                    rem_est = max(5.0, (rem_steps * step_rate) + 12.0) # +12s for VAE decode
                                    job["estimated_remaining_seconds"] = round(rem_est, 1)
                                    job["eta_text"] = self.stats.format_eta(rem_est)

                            elif mtype == "execution_error":
                                err_msg = mdata.get("exception_message", "ComfyUI execution error")
                                logger.error(f"Execution error on prompt {prompt_id}: {err_msg}")
                                job["error"] = err_msg

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"WebSocket monitor exception: {e}")
