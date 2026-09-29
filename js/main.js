import { loadContent, loadManifest, DataLoadError } from "./dataLoader.js";
import { renderImagePage, renderList, renderPost } from "./renderer.js";
import { parseHash, startRouter } from "./router.js";
import { hideStatus, showEmpty, showError, showLoading } from "./ui-states.js";
import { latestAnnouncementDate, lawType, toBuddhistDate, withinDays } from "./utils.js";

const status = document.querySelector("#status");
const listing = document.querySelector("#listing");
const cards = document.querySelector("#cards");
const postView = document.querySelector("#post");
const search = document.querySelector("#search");
const typeFilters = document.querySelector("#typeFilters");
const dateFilters = document.querySelector("#dateFilters");
const resultCount = document.querySelector("#resultCount");

const DATE_RANGES = [
  ["all", "ทั้งหมด"],
  ["7", "7 วัน"],
  ["30", "30 วัน"],
  ["90", "90 วัน"],
];

let posts = [];
let query = "";
let selectedType = "ทั้งหมด";
let selectedDays = "all";
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

function buildFilters() {
  const types = ["ทั้งหมด", ...new Set(posts.map((post) => lawType(post.title)))];
  typeFilters.innerHTML = "";
  for (const type of types) {
    typeFilters.append(chip(type, type === selectedType, () => {
      selectedType = type;
      draw();
    }));
  }
  dateFilters.innerHTML = "";
  for (const [value, label] of DATE_RANGES) {
    dateFilters.append(chip(label, value === selectedDays, () => {
      selectedDays = value;
      draw();
    }));
  }
}

function chip(label, active, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = active ? "chip active" : "chip";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function visiblePosts() {
  const needle = query.trim().toLocaleLowerCase("th");
  const reference = latestAnnouncementDate(posts);
  return posts.filter((post) => {
    if (selectedType !== "ทั้งหมด" && lawType(post.title) !== selectedType) return false;
    if (!withinDays(post.announcement_date, selectedDays, reference)) return false;
    if (!needle) return true;
    const haystack = `${post.title} ${(post.tags || []).join(" ")} ${toBuddhistDate(post.announcement_date)}`.toLocaleLowerCase("th");
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
  if (route.view === "post" || route.view === "image") {
    const post = posts.find((item) => item.roundDate === route.date && item.id === route.id);
    listing.hidden = true;
    if (!post) {
      postView.hidden = true;
      showError(status, "ไม่พบบทความนี้", () => { location.hash = "#/"; });
      return;
    }
    postView.hidden = false;
    postView.className = "post";
    if (route.view === "image") renderImagePage(post, route.kind, postView);
    else renderPost(post, postView);
    window.scrollTo(0, 0);
    return;
  }
  postView.className = "post";
  postView.hidden = true;
  listing.hidden = false;
  const shown = visiblePosts();
  resultCount.textContent = `${shown.length} บทความ`;
  buildFilters();
  if (!shown.length) {
    cards.innerHTML = `<p class="status empty">ไม่พบบทความตามตัวกรอง</p>`;
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
    buildFilters();
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
