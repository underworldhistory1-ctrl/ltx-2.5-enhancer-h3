let currentVideoPath = null;
let currentMode = 'refine';

document.addEventListener('DOMContentLoaded', () => {
  setupDropzone();
  setupControls();
  startStatusPolling();
  refreshJobs();
});

function setupDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');

  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleFileUpload(fileInput.files[0]);
    }
  });
}

async function handleFileUpload(file) {
  const dropzoneContent = document.querySelector('.dropzone-content');
  const progressContainer = document.getElementById('upload-progress-container');
  const progressBar = document.getElementById('upload-progress-bar');
  const statusText = document.getElementById('upload-status-text');

  dropzoneContent.style.display = 'none';
  progressContainer.style.display = 'block';
  progressBar.style.width = '10%';
  statusText.innerText = `Uploading ${file.name}...`;

  const formData = new FormData();
  formData.append('video', file);

  try {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload', true);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 90);
        progressBar.style.width = `${pct}%`;
        statusText.innerText = `Uploading... ${pct}%`;
      }
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        const data = JSON.parse(xhr.responseText);
        progressBar.style.width = '100%';
        statusText.innerText = 'Upload complete!';
        
        setTimeout(() => {
          progressContainer.style.display = 'none';
          dropzoneContent.style.display = 'flex';
          displaySourceVideo(data);
        }, 500);
      } else {
        alert('Upload failed: ' + xhr.responseText);
        progressContainer.style.display = 'none';
        dropzoneContent.style.display = 'flex';
      }
    };

    xhr.onerror = () => {
      alert('Upload failed due to network error.');
      progressContainer.style.display = 'none';
      dropzoneContent.style.display = 'flex';
    };

    xhr.send(formData);
  } catch (err) {
    alert('Upload error: ' + err);
    progressContainer.style.display = 'none';
    dropzoneContent.style.display = 'flex';
  }
}

function displaySourceVideo(data) {
  currentVideoPath = data.filepath;
  const card = document.getElementById('source-preview-card');
  const player = document.getElementById('source-video-player');
  const metaRes = document.getElementById('meta-res');
  const metaFps = document.getElementById('meta-fps');
  const metaDur = document.getElementById('meta-duration');
  const metaAudio = document.getElementById('meta-audio');

  player.src = data.url;
  const m = data.metadata || {};
  metaRes.innerText = `${m.width || '?'}x${m.height || '?'}`;
  metaFps.innerText = `${m.fps || 24} fps`;
  metaDur.innerText = `${m.duration ? m.duration.toFixed(1) : '?'}s`;
  metaAudio.innerText = m.has_audio ? 'Audio: Yes (Lossless)' : 'Audio: None';

  card.style.display = 'block';
  document.getElementById('enhance-btn').disabled = false;
}

function setupControls() {
  const modeBtns = document.querySelectorAll('.mode');
  modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentMode = btn.dataset.mode;
    });
  });

  const slider = document.getElementById('strength-slider');
  const valDisplay = document.getElementById('strength-val');
  slider.addEventListener('input', () => {
    valDisplay.innerText = parseFloat(slider.value).toFixed(2);
  });

  const enhanceBtn = document.getElementById('enhance-btn');
  enhanceBtn.addEventListener('click', submitEnhanceJob);
}

function appendPrompt(text) {
  const area = document.getElementById('positive-prompt');
  if (area.value) {
    area.value += ', ' + text;
  } else {
    area.value = text;
  }
}

function randomizeSeed() {
  document.getElementById('seed-input').value = Math.floor(Math.random() * 10000000);
}

async function submitEnhanceJob() {
  if (!currentVideoPath) {
    alert('Please upload a source video first.');
    return;
  }

  const btn = document.getElementById('enhance-btn');
  btn.disabled = true;

  const selectedRes = document.querySelector('input[name="resolution"]:checked').value;
  const strength = parseFloat(document.getElementById('strength-slider').value);
  const seed = parseInt(document.getElementById('seed-input').value) || 42;
  const promptText = document.getElementById('positive-prompt').value.trim();

  const payload = {
    input_video_path: currentVideoPath,
    mode: currentMode,
    resolution: selectedRes,
    lora_strength: strength,
    seed: seed,
    prompt: promptText
  };

  try {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      refreshJobs();
    } else {
      alert('Error creating job: ' + (data.error || 'Unknown error'));
      btn.disabled = false;
    }
  } catch (err) {
    alert('Failed to submit job: ' + err);
    btn.disabled = false;
  }
}

function startStatusPolling() {
  setInterval(updateGpuStatus, 2500);
  setInterval(refreshJobs, 1200);
}

async function updateGpuStatus() {
  try {
    const res = await fetch('/api/gpu_status');
    const data = await res.json();

    const conn = document.getElementById('connection');
    const connText = document.getElementById('connectionText');
    const vramText = document.getElementById('vram-text');

    vramText.innerText = `VRAM: ${(data.vram_used_mb / 1024).toFixed(1)} / ${(data.vram_total_mb / 1024).toFixed(0)} GB (${data.gpu_utilization_pct || 0}%)`;

    // Download banner
    const modelBanner = document.getElementById('model-download-banner');
    if (!data.model_ready && data.model_download_pct < 100) {
      modelBanner.style.display = 'flex';
      document.getElementById('model-progress-fill').style.width = `${data.model_download_pct}%`;
      document.getElementById('model-progress-text').innerText = `${data.model_download_gb} GB / 21.5 GB (${data.model_download_pct}%) • Any submitted jobs will safely queue and start automatically`;
    } else {
      modelBanner.style.display = 'none';
    }

    // Connection Dot & Status (H3 Style)
    if (data.h3_busy) {
      conn.className = 'connection busy';
      connText.innerText = 'H3 Active (Jobs Queue Safely)';
    } else if (data.external_gpu_busy) {
      conn.className = 'connection busy';
      connText.innerText = 'GPU Busy (Waiting...)';
    } else if (!data.model_ready) {
      conn.className = 'connection down';
      connText.innerText = 'Downloading Model...';
    } else {
      conn.className = 'connection ready';
      connText.innerText = 'Ready • RTX 5090';
    }

    // Benchmark stats
    if (data.stats && data.stats.rates) {
      const hdRate = data.stats.rates.FullHD || 5.0;
      const renders = data.stats.total_renders || 0;
      const summaryPill = document.getElementById('benchmark-pill');
      if (summaryPill) {
        summaryPill.innerText = `⚡ Speed: ~${hdRate}s per 1s video (${renders} renders learned)`;
      }
    }
  } catch (e) {
    console.warn('Status poll error:', e);
  }
}

async function refreshJobs() {
  try {
    const res = await fetch('/api/jobs');
    const data = await res.json();

    const jobsList = document.getElementById('jobs-list');
    const queueSummary = document.getElementById('queue-summary');
    const historyList = document.getElementById('history-list');
    const historyCount = document.getElementById('history-count');

    // 1. Render Active & Queued Jobs
    let queueItems = [];
    if (data.active) queueItems.push(data.active);
    if (data.queued) queueItems = queueItems.concat(data.queued);

    const activeCount = data.active ? 1 : 0;
    const queuedCount = data.queued ? data.queued.length : 0;

    if (queueItems.length === 0) {
      queueSummary.innerText = 'Idle';
      jobsList.innerHTML = '<div class="empty-state">No jobs currently processing. Upload a video on the left to start.</div>';
    } else {
      queueSummary.innerText = activeCount > 0 ? `Running (1 active, ${queuedCount} queued)` : `${queuedCount} queued`;
      jobsList.innerHTML = '';
      queueItems.forEach(job => {
        const el = createActiveJobElement(job);
        jobsList.appendChild(el);
      });
    }

    // 2. Render Completed & Failed Generations History
    const completedList = data.completed || [];
    historyCount.innerText = `${completedList.length} completed`;

    if (completedList.length === 0) {
      historyList.innerHTML = '<div class="empty-state">No completed generations yet.</div>';
    } else {
      historyList.innerHTML = '';
      completedList.forEach(job => {
        const hEl = createHistoryElement(job);
        historyList.appendChild(hEl);
      });

      // Show latest output video in player if available
      const latestSuccess = completedList.find(j => j.status === 'COMPLETED' && j.output_video_url);
      if (latestSuccess) {
        showOutputVideo(latestSuccess.output_video_url, latestSuccess.id);
      }
    }

    if (currentVideoPath) {
      document.getElementById('enhance-btn').disabled = false;
    }
  } catch (e) {
    console.warn('Refresh jobs error:', e);
  }
}

function createActiveJobElement(job) {
  const div = document.createElement('div');
  div.className = 'job-item';

  const modeBadge = job.mode === 'refine' ? 'Refine Details' : 'Restore';
  const queuePos = job.queue_position ? ` #${job.queue_position}` : '';
  
  let elapsedStr = '';
  if (job.started_at && job.status === 'RUNNING') {
    const elapsedSecs = Math.max(0, Math.floor(Date.now() / 1000 - job.started_at));
    const mins = Math.floor(elapsedSecs / 60);
    const secs = elapsedSecs % 60;
    elapsedStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  }

  let stepDisplay = '';
  if (job.step_current && job.step_max) {
    stepDisplay = `<span class="job-step-badge">Step ${job.step_current} / ${job.step_max}</span>`;
  }

  div.innerHTML = `
    <div class="job-header">
      <div class="job-header-left">
        <span class="job-id">${job.id}</span>
        <span class="job-spec">(${modeBadge} • ${job.resolution})</span>
      </div>
      <div class="job-header-right">
        ${stepDisplay}
        <span class="job-status-tag ${job.status}">${job.status}${job.status === 'QUEUED' ? queuePos : ''}</span>
      </div>
    </div>
    <div class="job-stage">${job.stage || 'In progress...'}</div>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" style="width: ${job.progress || 0}%;"></div>
    </div>
    <div class="live-time-ticker">
      ${elapsedStr ? `<span class="ticker-elapsed">⏱️ Elapsed: <strong>${elapsedStr}</strong></span>` : ''}
      <span class="ticker-remaining">⏳ Remaining: <strong>${job.eta_text || 'Estimating...'}</strong></span>
    </div>
  `;
  return div;
}

function createHistoryElement(job) {
  const div = document.createElement('div');
  div.className = 'history-item';

  const modeBadge = job.mode === 'refine' ? 'Refine' : 'Restore';
  const vInfo = job.video_info || {};
  const dur = vInfo.duration ? `${vInfo.duration.toFixed(1)}s video` : '';
  const elapsed = job.elapsed_seconds ? ` • Took ${Math.round(job.elapsed_seconds)}s` : '';

  div.innerHTML = `
    <div class="history-item-left">
      <div class="history-meta-title">
        <span>${job.id}</span>
        <span class="job-status-tag ${job.status}">${job.status}</span>
      </div>
      <div class="history-sub">
        ${modeBadge} • ${job.resolution} ${dur ? '• ' + dur : ''}${elapsed}
        ${job.error ? `<div style="color: var(--bad); margin-top: 4px; word-break: break-all;">❌ Error: ${job.error}</div>` : ''}
      </div>
    </div>
    <div class="history-actions">
      ${job.output_video_url ? `
        <button class="action-btn play-btn" onclick="showOutputVideo('${job.output_video_url}', '${job.id}')">
          ▶️ Play
        </button>
        <a class="action-btn" href="${job.output_video_url}" download="enhanced_${job.id}.mp4">
          ⬇️ Download
        </a>
      ` : ''}
      <button class="action-btn delete-btn" onclick="deleteJob('${job.id}')">
        🗑️ Delete
      </button>
    </div>
  `;
  return div;
}

async function deleteJob(jobId) {
  if (!confirm(`Delete generation ${jobId}?`)) return;
  try {
    const res = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      refreshJobs();
    } else {
      alert('Failed to delete job.');
    }
  } catch (e) {
    alert('Error deleting job: ' + e);
  }
}

function showOutputVideo(url, jobId) {
  const card = document.getElementById('output-result-card');
  const player = document.getElementById('output-video-player');
  const downloadBtn = document.getElementById('download-btn');
  const title = document.getElementById('player-title');

  if (jobId) {
    title.innerText = `Enhanced Video — ${jobId}`;
  }

  if (player.src !== window.location.origin + url) {
    player.src = url;
    downloadBtn.href = url;
    card.style.display = 'block';
    player.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function openDocsModal() {
  document.getElementById('docs-modal').style.display = 'grid';
}

function closeDocsModal() {
  document.getElementById('docs-modal').style.display = 'none';
}
