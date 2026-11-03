(() => {
  const base = "/plugins/open_tech_quest/assets/branding";
  document
    .querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"]')
    .forEach((link) => link.remove());
  for (const [rel, type, sizes, file] of [
    ["icon", "image/png", "32x32", "favicon-32.png"],
    ["icon", "image/svg+xml", "any", "favicon.svg"],
    ["apple-touch-icon", "image/png", "180x180", "apple-touch-icon.png"],
  ]) {
    const link = document.createElement("link");
    link.rel = rel;
    link.type = type;
    link.setAttribute("sizes", sizes);
    link.href = `${base}/${file}`;
    document.head.appendChild(link);
  }
})();
