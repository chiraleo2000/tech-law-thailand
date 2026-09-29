export function parseHash(hash = location.hash) {
  const value = hash || "#/";
  const image = /^#\/post\/([^/]+)\/([^/]+)\/image\/(infographic|relationship)$/.exec(value);
  if (image) {
    return {
      view: "image",
      date: decodeURIComponent(image[1]),
      id: decodeURIComponent(image[2]),
      kind: image[3],
    };
  }
  const post = /^#\/post\/([^/]+)\/([^/]+)$/.exec(value);
  if (!post) return { view: "list" };
  return {
    view: "post",
    date: decodeURIComponent(post[1]),
    id: decodeURIComponent(post[2]),
  };
}

export function startRouter(render) {
  const run = () => render(parseHash());
  window.addEventListener("hashchange", run);
  if (!location.hash) location.hash = "#/";
  else run();
  return run;
}
