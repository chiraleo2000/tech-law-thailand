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

const LAW_TYPES = [
  ["ร่างกฎหมาย", /^ร่าง/],
  ["พระราชบัญญัติ", /^(พรบ\.|พ\.ร\.บ\.|พระราชบัญญัติ)/],
  ["พระราชกฤษฎีกา", /^(พรฎ\.|พ\.ร\.ฎ\.|พระราชกฤษฎีกา)/],
  ["ระเบียบ", /^ระเบียบ/],
  ["หลักเกณฑ์", /^(หลักเกณฑ์|ประกาศ)/],
];

export function lawType(title) {
  const name = title || "";
  const found = LAW_TYPES.find(([, pattern]) => pattern.test(name));
  return found ? found[0] : "อื่น ๆ";
}

export function latestAnnouncementDate(posts) {
  return posts.reduce((latest, post) => (
    post.announcement_date > latest ? post.announcement_date : latest
  ), "");
}

export function withinDays(iso, days, referenceIso) {
  if (!days || days === "all") return true;
  if (!iso || !referenceIso) return false;
  const reference = Date.parse(`${referenceIso}T00:00:00Z`);
  const current = Date.parse(`${iso}T00:00:00Z`);
  if (Number.isNaN(reference) || Number.isNaN(current)) return false;
  const elapsed = (reference - current) / 86400000;
  return elapsed >= 0 && elapsed <= Number(days);
}

export function firstSectionExcerpt(html, limit = 220) {
  const doc = new DOMParser().parseFromString(`<div>${html || ""}</div>`, "text/html");
  const headings = [...doc.body.querySelectorAll("h1, h2, h3")];
  const heading = headings.find((item) => /วัตถุประสงค์/.test(item.textContent || "")) || headings[0];
  let node = heading ? heading.nextElementSibling : doc.body.querySelector("p");
  while (node && !(node.textContent || "").trim()) node = node.nextElementSibling;
  let text = (node?.textContent || "").replace(/\s+/g, " ").trim();
  if (text.length > limit) text = `${text.slice(0, limit).trim()}…`;
  return text;
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
