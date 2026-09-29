import { assetUrl, lawType, sanitizeHtml, sortPosts, toBuddhistDate } from "./utils.js";

export function renderList(posts, container, onOpen) {
  const visible = sortPosts(posts);
  container.innerHTML = "";
  for (const post of visible) {
    const card = document.createElement("a");
    card.className = "card";
    card.href = postHref(post);
    card.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      onOpen(post);
    });
    const date = document.createElement("p");
    date.className = "card-date";
    date.textContent = toBuddhistDate(post.announcement_date);
    const kind = document.createElement("span");
    kind.className = "type-badge";
    kind.textContent = lawType(post.title);
    const title = document.createElement("h2");
    title.textContent = post.title;
    card.append(date, kind, title);
    if (post.tags && post.tags.length) {
      const tags = document.createElement("p");
      tags.className = "tags";
      tags.textContent = post.tags.slice(0, 4).map((tag) => `#${tag}`).join(" ");
      card.append(tags);
    }
    container.append(card);
  }
}

export function renderPost(post, container) {
  container.innerHTML = "";
  const header = document.createElement("header");
  header.className = "post-header";
  const back = document.createElement("a");
  back.className = "back";
  back.href = "#/";
  back.textContent = "กลับสู่รายการ";
  const title = document.createElement("h2");
  title.textContent = post.title;
  const date = document.createElement("p");
  date.className = "announcement-date";
  date.textContent = `วันที่ประกาศ ${toBuddhistDate(post.announcement_date)}`;
  header.append(back, title, date);

  const body = document.createElement("div");
  body.className = "content";
  body.innerHTML = sanitizeHtml(post.content_html);

  const figures = document.createElement("div");
  figures.className = "figures";
  appendFigure(figures, post, post.infographic_image, `อินโฟกราฟิกแนวตั้งของ${post.title}`, "portrait");
  appendFigure(figures, post, post.relationship_image, `แผนผังความสัมพันธ์ของ${post.title}`, "wide");

  container.append(header, body);
  if (figures.childElementCount) container.append(figures);
  appendComments(container, post.comments);
}

export function imageHref(post, kind) {
  return `#/post/${encodeURIComponent(post.roundDate)}/${encodeURIComponent(post.id)}/image/${kind}`;
}

export function renderImagePage(post, kind, container) {
  const relative = kind === "relationship" ? post.relationship_image : post.infographic_image;
  const alt = kind === "relationship"
    ? `แผนผังความสัมพันธ์ของ${post.title}`
    : `อินโฟกราฟิกแนวตั้งของ${post.title}`;
  container.innerHTML = "";
  container.classList.add("image-page", kind === "relationship" ? "wide" : "portrait");
  const back = document.createElement("a");
  back.className = "back";
  back.href = postHref(post);
  back.textContent = "กลับสู่บทความ";
  const title = document.createElement("h2");
  title.textContent = alt;
  container.append(back, title);
  const src = assetUrl(post.contentPath, relative);
  if (!src) return;
  const image = document.createElement("img");
  image.src = src;
  image.alt = alt;
  container.append(image);
}

function appendFigure(parent, post, relativePath, alt, kind) {
  const src = assetUrl(post.contentPath, relativePath);
  if (!src) return;
  const figure = document.createElement("figure");
  figure.className = kind;
  const link = document.createElement("a");
  link.href = imageHref(post, kind === "wide" ? "relationship" : "infographic");
  link.className = "figure-link";
  const image = document.createElement("img");
  image.src = src;
  image.alt = alt;
  link.append(image);
  const caption = document.createElement("figcaption");
  caption.textContent = `${alt} · คลิกเพื่อดูภาพขนาดเต็ม`;
  figure.append(link, caption);
  parent.append(figure);
}

function appendComments(container, comments) {
  const lines = (comments || []).filter((item) => typeof item === "string" && item.trim());
  if (!lines.length) return;
  const section = document.createElement("section");
  section.className = "comments";
  const heading = document.createElement("h3");
  heading.textContent = "ความเห็น";
  section.append(heading);
  for (const line of lines) {
    const block = document.createElement("pre");
    block.textContent = line;
    section.append(block);
  }
  container.append(section);
}

export function postHref(post) {
  return `#/post/${encodeURIComponent(post.roundDate)}/${encodeURIComponent(post.id)}`;
}
