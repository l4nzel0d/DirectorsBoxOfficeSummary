// Box Office Summary page: chart tooltip + sortable filmography table.
// Text that comes from the data is inserted with textContent, never innerHTML.

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// --- Chart: crosshair + tooltip for the hovered/focused film column --------
for (const chart of document.querySelectorAll(".chart-inner")) {
  const svg = chart.querySelector("svg");
  const tip = chart.querySelector(".tooltip");
  const crosshair = svg.querySelector(".crosshair");
  const width = svg.viewBox.baseVal.width;

  // The <title>s are the no-JS fallback; drop them so tooltips don't double up.
  svg.querySelectorAll(".hit title").forEach((title) => title.remove());

  const row = (series, value, label) => {
    const line = element("div", "tip-row");
    line.append(element("i", `line-key ${series}`), element("b", "", value), element("span", "", label));
    return line;
  };

  const show = (hit) => {
    const { x, title, year, ww, dom } = hit.dataset;
    crosshair.setAttribute("x1", x);
    crosshair.setAttribute("x2", x);
    crosshair.classList.add("on");

    tip.replaceChildren(element("div", "tip-title", title));
    if (year) tip.append(element("div", "tip-year", year));
    tip.append(row("worldwide", ww, "Worldwide"), row("domestic", dom, "Domestic"));
    tip.hidden = false;

    // Beside the crosshair, flipping to its left when it would overflow.
    const px = (x / width) * svg.getBoundingClientRect().width;
    let left = px + 12;
    if (left + tip.offsetWidth > chart.clientWidth) left = px - 12 - tip.offsetWidth;
    tip.style.left = `${Math.max(0, left)}px`;
  };

  const hide = () => {
    tip.hidden = true;
    crosshair.classList.remove("on");
  };

  for (const hit of svg.querySelectorAll(".hit")) {
    hit.addEventListener("pointerenter", () => show(hit));
    hit.addEventListener("focus", () => show(hit));
    hit.addEventListener("blur", hide);
  }
  svg.addEventListener("pointerleave", hide);
}

// --- Filmography: click a header to sort; missing values always sort last --
for (const table of document.querySelectorAll("table.films")) {
  const body = table.tBodies[0];
  const headers = [...table.tHead.rows[0].cells];

  headers.forEach((th, column) => {
    th.querySelector("button").addEventListener("click", () => {
      const current = th.getAttribute("aria-sort");
      const direction = current ? (current === "ascending" ? "descending" : "ascending") : th.dataset.first;
      headers.forEach((header) => header.removeAttribute("aria-sort"));
      th.setAttribute("aria-sort", direction);

      const sign = direction === "ascending" ? 1 : -1;
      const numeric = th.dataset.type === "num";
      const key = (tr) => tr.cells[column].dataset.sort;
      const rank = (tr) => Number(tr.dataset.rank);
      const rows = [...body.rows].sort((a, b) => {
        const ka = key(a);
        const kb = key(b);
        if (ka === "" || kb === "") return (ka === "") - (kb === "") || rank(a) - rank(b);
        const order = numeric ? Number(ka) - Number(kb) : ka.localeCompare(kb);
        return sign * order || rank(a) - rank(b);
      });
      body.append(...rows);
    });
  });
}
