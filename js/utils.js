const ALLOWED = new Set([
  "h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "thead", "tbody", "tr", "th", "td",
  "ul", "ol", "li", "strong", "em", "b", "i", "a", "br", "blockquote",
]);

export function toBuddhistDate(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  if (!match) return iso || "";
  const year = Number(match[1]) + 543;
  const month = Number(match[2]);
  const day = Number(match[3]);
  return `${day}/${month}/${year}`;
}

export function sortPosts(posts) {
  return [...posts].sort((a, b) => {
    if (a.announcement_date !== b.announcement_date) {
      return a.announcement_date < b.announcement_date ? 1 : -1;
    }
    return (a.title || "").localeCompare(b.title || "", "th");
  });
}

export function sanitizeHtml(html) {
  const doc = new DOMParser().parseFromString(`<div>${html || ""}</div>`, "text/html");
  const source = doc.body.firstElementChild;
  const clean = document.createElement("div");
  if (source) copyChildren(source, clean);
  return clean.innerHTML;
}

function copyChildren(source, target) {
  for (const node of [...source.childNodes]) {
    if (node.nodeType === Node.TEXT_NODE) {
      target.append(document.createTextNode(node.textContent));
      continue;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) continue;
    const name = node.tagName.toLowerCase();
    if (!ALLOWED.has(name)) {
      copyChildren(node, target);
      continue;
    }
    const el = document.createElement(name);
    if (name === "a") {
      const href = node.getAttribute("href") || "";
      if (/^https?:/i.test(href)) {
        el.setAttribute("href", href);
        el.setAttribute("rel", "noopener noreferrer");
      }
    }
    copyChildren(node, el);
    target.append(el);
  }
}

export function contentDirectory(contentPath) {
  const index = contentPath.lastIndexOf("/");
  return index >= 0 ? contentPath.slice(0, index + 1) : "";
}

export function assetUrl(contentPath, relativePath) {
  if (!relativePath) return "";
  return `${contentDirectory(contentPath)}${relativePath}`;
}
