export function parseHash(hash = location.hash) {
  const value = hash || "#/";
  const match = /^#\/post\/([^/]+)\/(.+)$/.exec(value);
  if (!match) return { view: "list" };
  return {
    view: "post",
    date: decodeURIComponent(match[1]),
    id: decodeURIComponent(match[2]),
  };
}

export function startRouter(render) {
  const run = () => render(parseHash());
  window.addEventListener("hashchange", run);
  if (!location.hash) location.hash = "#/";
  else run();
  return run;
}
