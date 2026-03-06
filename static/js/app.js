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

      if (!response.ok) {
        return;
      }

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
      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
      }
    });
  }
});
