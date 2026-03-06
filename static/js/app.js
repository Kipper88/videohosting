document.addEventListener("DOMContentLoaded", () => {
  const actions = document.querySelector(".actions[data-video-id]");
  if (!actions) return;

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
});
