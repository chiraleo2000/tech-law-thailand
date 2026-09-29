export class DataLoadError extends Error {
  constructor(message) {
    super(message);
    this.name = "DataLoadError";
  }
}

export async function loadManifest() {
  return readJson("./data/manifest.json", "โหลดสารบัญเนื้อหาไม่สำเร็จ");
}

export async function loadContent(contentPath) {
  return readJson(`./${contentPath}`, "โหลดเนื้อหาบทความไม่สำเร็จ");
}

async function readJson(url, message) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(String(response.status));
    return await response.json();
  } catch (error) {
    if (error instanceof DataLoadError) throw error;
    throw new DataLoadError(message);
  }
}
