import { loadContent, loadManifest, DataLoadError } from "./dataLoader.js";
import { renderList, renderPost } from "./renderer.js";
import { parseHash, startRouter } from "./router.js";
import { hideStatus, showEmpty, showError, showLoading } from "./ui-states.js";

const status = document.querySelector("#status");
const listing = document.querySelector("#listing");
const cards = document.querySelector("#cards");
const postView = document.querySelector("#post");
const search = document.querySelector("#search");

let posts = [];
let query = "";
let ready = false;

async function loadAll() {
  showLoading(status);
  listing.hidden = true;
  postView.hidden = true;
  const manifest = await loadManifest();
  const entries = Array.isArray(manifest.entries) ? manifest.entries : [];
  const documents = await Promise.all(entries.map((entry) => loadContent(entry.path)));
  posts = documents.flatMap((document, index) => {
    const contentPath = entries[index].path;
    return (document.posts || []).map((post) => ({
      ...post,
      roundDate: document.date,
      contentPath,
    }));
  });
}

function visiblePosts() {
  const needle = query.trim().toLocaleLowerCase("th");
  if (!needle) return posts;
  return posts.filter((post) => {
    const haystack = `${post.title} ${(post.tags || []).join(" ")}`.toLocaleLowerCase("th");
    return haystack.includes(needle);
  });
}

function draw(route = parseHash()) {
  hideStatus(status);
  if (!posts.length) {
    listing.hidden = true;
    postView.hidden = true;
    showEmpty(status);
    return;
  }
  if (route.view === "post") {
    const post = posts.find((item) => item.roundDate === route.date && item.id === route.id);
    listing.hidden = true;
    if (!post) {
      postView.hidden = true;
      showError(status, "ไม่พบบทความนี้", () => { location.hash = "#/"; });
      return;
    }
    postView.hidden = false;
    renderPost(post, postView);
    window.scrollTo(0, 0);
    return;
  }
  postView.hidden = true;
  listing.hidden = false;
  const shown = visiblePosts();
  if (!shown.length) {
    cards.innerHTML = "";
    showEmpty(status);
    return;
  }
  renderList(shown, cards, (post) => {
    location.hash = `#/post/${encodeURIComponent(post.roundDate)}/${encodeURIComponent(post.id)}`;
  });
}

async function boot() {
  try {
    await loadAll();
    ready = true;
    draw();
  } catch (error) {
    const message = error instanceof DataLoadError ? error.message : "โหลดเนื้อหาไม่สำเร็จ";
    listing.hidden = true;
    postView.hidden = true;
    showError(status, message, () => { boot(); });
  }
}

search.addEventListener("input", () => {
  query = search.value;
  if (parseHash().view === "list") draw();
});

startRouter(() => {
  if (ready) draw();
});

boot();
