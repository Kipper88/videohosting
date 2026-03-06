document.addEventListener("DOMContentLoaded", () => {
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

      const objectUrl = URL.createObjectURL(file);
      currentObjectUrl = objectUrl;
      uploadPreview.src = objectUrl;
      uploadPreviewWrap.classList.add("ready");
      uploadPreviewPlaceholder.textContent = "Предпросмотр выбранного видео";
      uploadPreview.onloadeddata = () => {
        uploadPreview.currentTime = 0;
      };
    });

    window.addEventListener("beforeunload", () => {
      if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
    });
  }

  const player = document.querySelector("[data-player]");
  if (player) {
    const mainVideo = player.querySelector("[data-main-video]");
    const previewVideo = player.querySelector("[data-preview-video]");
    const playToggle = player.querySelector("[data-play-toggle]");
    const progress = player.querySelector("[data-progress]");
    const progressWrap = player.querySelector("[data-progress-wrap]");
    const timeLabel = player.querySelector("[data-time-label]");
    const previewPopover = player.querySelector("[data-preview-popover]");
    const previewCanvas = player.querySelector("[data-preview-canvas]");
    const previewTime = player.querySelector("[data-preview-time]");
    const storyboardTrack = document.querySelector("[data-storyboard-track]");

    const previewCtx = previewCanvas.getContext("2d");

    const formatTime = (sec) => {
      if (!Number.isFinite(sec)) return "0:00";
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${m}:${String(s).padStart(2, "0")}`;
    };

    const updateTimeLabel = () => {
      timeLabel.textContent = `${formatTime(mainVideo.currentTime)} / ${formatTime(mainVideo.duration)}`;
    };

    playToggle.addEventListener("click", () => {
      if (mainVideo.paused) {
        mainVideo.play();
      } else {
        mainVideo.pause();
      }
    });

    mainVideo.addEventListener("play", () => {
      playToggle.textContent = "⏸";
    });

    mainVideo.addEventListener("pause", () => {
      playToggle.textContent = "▶";
    });

    mainVideo.addEventListener("timeupdate", () => {
      if (!mainVideo.duration) return;
      progress.value = String(Math.floor((mainVideo.currentTime / mainVideo.duration) * 1000));
      updateTimeLabel();
    });

    mainVideo.addEventListener("loadedmetadata", async () => {
      updateTimeLabel();
      if (!storyboardTrack || !mainVideo.duration) return;

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
            ctx.drawImage(previewVideo, 0, 0, canvas.width, canvas.height);
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
      previewVideo.onseeked = () => {
        previewCtx.drawImage(previewVideo, 0, 0, previewCanvas.width, previewCanvas.height);
      };
    });

    progressWrap.addEventListener("mouseleave", () => {
      previewPopover.style.display = "none";
    });
  }
});
