document.addEventListener("DOMContentLoaded", () => {
  const layout = document.getElementById("app-layout");
  const sidebarToggle = document.getElementById("sidebar-toggle");
  const sidebarCollapsed = localStorage.getItem("yclone_sidebar_collapsed") === "true";
  if (layout && sidebarCollapsed) layout.classList.add("sidebar-collapsed");
  sidebarToggle?.addEventListener("click", () => {
    layout?.classList.toggle("sidebar-collapsed");
    localStorage.setItem("yclone_sidebar_collapsed", String(layout?.classList.contains("sidebar-collapsed")));
  });

  const persistedVolume = Number(localStorage.getItem("yclone_volume") ?? "0.7");
  const persistedMuted = (localStorage.getItem("yclone_muted") ?? "false") === "true";

  const actions = document.querySelector(".actions[data-video-id]");
  if (actions) {
    const videoId = actions.getAttribute("data-video-id");
    const likeBtn = actions.querySelector('[data-action="like"]');
    const dislikeBtn = actions.querySelector('[data-action="dislike"]');

    async function sendReaction(action) {
      const response = await fetch(`/api/videos/${videoId}/react`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
        credentials: "same-origin",
      });
      if (!response.ok) return;
      const data = await response.json();
      likeBtn.querySelector(".likes-count").textContent = data.likes;
      dislikeBtn.querySelector(".dislikes-count").textContent = data.dislikes;
      likeBtn.classList.toggle("active", data.user_reaction === 1);
      dislikeBtn.classList.toggle("active", data.user_reaction === -1);
    }

    likeBtn?.addEventListener("click", () => sendReaction("like"));
    dislikeBtn?.addEventListener("click", () => sendReaction("dislike"));
  }


  const uploadInput = document.querySelector('input[type="file"][name="file"]');
  const uploadPreviewWrap = document.querySelector(".upload-preview-wrap");
  const uploadPreview = document.querySelector("#upload-preview-video");
  const uploadPreviewPlaceholder = document.querySelector(".upload-preview-placeholder");

  if (uploadInput && uploadPreviewWrap && uploadPreview && uploadPreviewPlaceholder) {
    let currentObjectUrl = null;
    uploadInput.addEventListener("change", () => {
      const file = uploadInput.files?.[0];
      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
        currentObjectUrl = null;
      }
      if (!file) {
        uploadPreview.removeAttribute("src");
        uploadPreview.load();
        uploadPreviewWrap.classList.remove("ready");
        uploadPreviewPlaceholder.textContent = "Выберите файл, чтобы увидеть предпросмотр";
        return;
      }
      currentObjectUrl = URL.createObjectURL(file);
      uploadPreview.src = currentObjectUrl;
      uploadPreviewWrap.classList.add("ready");
      uploadPreviewPlaceholder.textContent = "Предпросмотр выбранного видео";
      uploadPreview.onloadeddata = () => { uploadPreview.currentTime = 0; };
    });
    window.addEventListener("beforeunload", () => {
      if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
    });
  }

  const drawContain = (ctx, video, cw, ch) => {
    const vw = video.videoWidth || 16;
    const vh = video.videoHeight || 9;
    const vr = vw / vh;
    const cr = cw / ch;
    let dw = cw;
    let dh = ch;
    if (vr > cr) dh = cw / vr; else dw = ch * vr;
    const dx = (cw - dw) / 2;
    const dy = (ch - dh) / 2;
    ctx.clearRect(0, 0, cw, ch);
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, cw, ch);
    ctx.drawImage(video, dx, dy, dw, dh);
  };

  const player = document.querySelector("[data-player]");
  if (player) {
    const mainVideo = player.querySelector("[data-main-video]");
    const previewVideo = player.querySelector("[data-preview-video]");
    const playToggle = player.querySelector("[data-play-toggle]");
    const backwardBtn = player.querySelector("[data-backward]");
    const forwardBtn = player.querySelector("[data-forward]");
    const progress = player.querySelector("[data-progress]");
    const progressWrap = player.querySelector("[data-progress-wrap]");
    const timeLabel = player.querySelector("[data-time-label]");
    const previewPopover = player.querySelector("[data-preview-popover]");
    const previewCanvas = player.querySelector("[data-preview-canvas]");
    const previewTime = player.querySelector("[data-preview-time]");
    const storyboardTrack = document.querySelector("[data-storyboard-track]");
    const volumeSlider = player.querySelector("[data-volume]");
    const fullscreenBtn = player.querySelector("[data-fullscreen]");
    const speedSelect = player.querySelector("[data-speed]");

    if (!mainVideo || !previewVideo || !progress || !progressWrap || !timeLabel || !previewPopover || !previewCanvas || !previewTime) {
      return;
    }

    const previewCtx = previewCanvas.getContext("2d");
    mainVideo.volume = Number.isFinite(persistedVolume) ? Math.min(Math.max(persistedVolume, 0), 1) : 0.7;
    mainVideo.muted = persistedMuted;
    if (volumeSlider) volumeSlider.value = String(Math.round(mainVideo.volume * 100));

    const formatTime = (sec) => {
      if (!Number.isFinite(sec)) return "0:00";
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = Math.floor(sec % 60);
      if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
      return `${m}:${String(s).padStart(2, "0")}`;
    };

    const updateTimeLabel = () => {
      timeLabel.textContent = `${formatTime(mainVideo.currentTime)} / ${formatTime(mainVideo.duration)}`;
    };

    const togglePlay = () => (mainVideo.paused ? mainVideo.play() : mainVideo.pause());
    playToggle?.addEventListener("click", togglePlay);
    mainVideo.addEventListener("click", togglePlay);

    backwardBtn?.addEventListener("click", () => { mainVideo.currentTime = Math.max(mainVideo.currentTime - 10, 0); });
    forwardBtn?.addEventListener("click", () => { mainVideo.currentTime = Math.min(mainVideo.currentTime + 10, mainVideo.duration || mainVideo.currentTime + 10); });

    mainVideo.addEventListener("play", () => { playToggle.classList.add("is-playing"); });
    mainVideo.addEventListener("pause", () => { playToggle.classList.remove("is-playing"); });

    mainVideo.addEventListener("dblclick", () => {
      if (!document.fullscreenElement) player.requestFullscreen?.();
      else document.exitFullscreen?.();
    });

    fullscreenBtn?.addEventListener("click", () => {
      if (!document.fullscreenElement) player.requestFullscreen?.();
      else document.exitFullscreen?.();
    });

    speedSelect?.addEventListener("change", () => { mainVideo.playbackRate = Number(speedSelect.value) || 1; });

    volumeSlider?.addEventListener("input", () => {
      const vol = Number(volumeSlider.value) / 100;
      mainVideo.volume = vol;
      mainVideo.muted = vol === 0;
      localStorage.setItem("yclone_volume", String(vol));
      localStorage.setItem("yclone_muted", String(mainVideo.muted));
    });

    mainVideo.addEventListener("volumechange", () => {
      localStorage.setItem("yclone_volume", String(mainVideo.volume));
      localStorage.setItem("yclone_muted", String(mainVideo.muted));
      if (volumeSlider) volumeSlider.value = String(Math.round(mainVideo.volume * 100));
    });

    mainVideo.addEventListener("timeupdate", () => {
      if (!mainVideo.duration) return;
      progress.value = String(Math.floor((mainVideo.currentTime / mainVideo.duration) * 1000));
      updateTimeLabel();
    });

    mainVideo.addEventListener("loadedmetadata", async () => {
      updateTimeLabel();
      if (!storyboardTrack || !mainVideo.duration) return;
      storyboardTrack.innerHTML = "";
      const snapshots = 10;
      for (let i = 0; i < snapshots; i += 1) {
        const t = (mainVideo.duration * i) / (snapshots - 1 || 1);
        await new Promise((resolve) => {
          previewVideo.currentTime = Math.min(t, Math.max(mainVideo.duration - 0.1, 0));
          previewVideo.onseeked = () => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "story-item";
            item.innerHTML = `<canvas width="160" height="90"></canvas><span>${formatTime(t)}</span>`;
            const canvas = item.querySelector("canvas");
            const ctx = canvas.getContext("2d");
            drawContain(ctx, previewVideo, canvas.width, canvas.height);
            item.addEventListener("click", () => {
              mainVideo.currentTime = t;
              if (mainVideo.paused) mainVideo.play();
            });
            storyboardTrack.appendChild(item);
            resolve();
          };
        });
      }
      previewVideo.currentTime = 0;
    });

    progress.addEventListener("input", () => {
      if (!mainVideo.duration) return;
      mainVideo.currentTime = (Number(progress.value) / 1000) * mainVideo.duration;
    });

    progressWrap.addEventListener("mousemove", (event) => {
      if (!mainVideo.duration) return;
      const rect = progress.getBoundingClientRect();
      const relative = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
      const ratio = rect.width ? relative / rect.width : 0;
      const target = ratio * mainVideo.duration;
      previewPopover.style.display = "flex";
      previewPopover.style.left = `${relative}px`;
      previewTime.textContent = formatTime(target);
      previewVideo.currentTime = target;
      previewVideo.onseeked = () => drawContain(previewCtx, previewVideo, previewCanvas.width, previewCanvas.height);
    });

    progressWrap.addEventListener("mouseleave", () => { previewPopover.style.display = "none"; });
  }

  document.querySelectorAll("[data-hover-preview]").forEach((card) => {
    const image = card.querySelector("[data-hover-image]");
    const video = card.querySelector("[data-hover-video]");
    const controls = card.querySelector("[data-hover-controls]");
    const range = card.querySelector("[data-hover-progress]");
    const muteBtn = card.querySelector("[data-hover-mute]");
    if (!image || !video || !controls || !range || !muteBtn) return;

    video.muted = true;
    let over = false;

    card.addEventListener("mouseenter", async () => {
      over = true;
      image.style.display = "none";
      video.style.display = "block";
      controls.style.display = "flex";
      try { await video.play(); } catch (_) {}
    });

    card.addEventListener("mouseleave", () => {
      over = false;
      video.pause();
      video.currentTime = 0;
      range.value = "0";
      image.style.display = "block";
      video.style.display = "none";
      controls.style.display = "none";
      video.muted = true;
    });

    video.addEventListener("timeupdate", () => {
      if (!video.duration || !over) return;
      range.value = String(Math.floor((video.currentTime / video.duration) * 1000));
    });

    range.addEventListener("input", () => {
      if (!video.duration) return;
      video.currentTime = (Number(range.value) / 1000) * video.duration;
    });

    muteBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      video.muted = !video.muted;
      muteBtn.classList.toggle("is-unmuted", !video.muted);
    });
  });

  document.querySelectorAll(".comment-item[data-comment-id]").forEach((node) => {
    const commentId = node.getAttribute("data-comment-id");
    const likeBtn = node.querySelector('[data-comment-action="like"]');
    const dislikeBtn = node.querySelector('[data-comment-action="dislike"]');
    const likesCount = node.querySelector(".comment-likes");
    const dislikesCount = node.querySelector(".comment-dislikes");
    if (!commentId || !likeBtn || !dislikeBtn) return;

    const react = async (action) => {
      const response = await fetch(`/api/comments/${commentId}/react`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
        credentials: "same-origin",
      });
      if (!response.ok) return;
      const data = await response.json();
      if (likesCount) likesCount.textContent = String(data.likes);
      if (dislikesCount) dislikesCount.textContent = String(data.dislikes);
    };

    likeBtn.addEventListener("click", () => react("like"));
    dislikeBtn.addEventListener("click", () => react("dislike"));
  });

  const shortsFeed = document.getElementById("shorts-feed");
  const shortsLoader = document.getElementById("shorts-loader");
  if (shortsFeed && shortsLoader) {
    let loading = false;
    let offset = Number(shortsFeed.getAttribute("data-offset") || "0");
    const limit = 8;

    const loadShorts = async () => {
      if (loading) return;
      loading = true;
      const response = await fetch(`/api/shorts?offset=${offset}&limit=${limit}`);
      if (!response.ok) {
        loading = false;
        return;
      }
      const payload = await response.json();
      const items = payload.items || [];
      if (items.length === 0) {
        shortsLoader.textContent = "Вы достигли конца ленты.";
        loading = false;
        return;
      }
      items.forEach((item) => {
        const card = document.createElement("article");
        card.className = "short-card fade-in";
        card.innerHTML = `
          <video controls preload="metadata">
            <source src="/uploads/${item.filename}" type="video/mp4" />
          </video>
          <h3>${item.title}</h3>
          <p>@${item.author} · ${item.views} просмотров</p>
        `;
        shortsFeed.appendChild(card);
      });
      offset += items.length;
      shortsFeed.setAttribute("data-offset", String(offset));
      loading = false;
    };

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadShorts();
    }, { rootMargin: "300px" });

    observer.observe(shortsLoader);
    loadShorts();
  }
});
