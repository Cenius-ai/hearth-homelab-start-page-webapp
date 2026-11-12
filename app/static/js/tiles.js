/** Tile rendering — the client renderer mirrors the Jinja tile partial. */

import { formatHostPort } from "./hostport.js";
import { statusDetail, statusLabel, statusTone } from "./formatting.js";

export function createTile(service) {
  const tile = document.createElement("li");
  tile.className = "tile";
  tile.dataset.serviceId = String(service.id);
  tile.dataset.categoryId = String(service.category_id);
  tile.dataset.search = `${service.name} ${service.url} ${formatHostPort(service)}`.toLowerCase();
  tile.draggable = true;

  const body = document.createElement("a");
  body.className = "tile__body";
  body.href = `/services/${service.id}`;

  const icon = document.createElement("span");
  icon.className = "tile__icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = service.icon || "🔗";

  const name = document.createElement("span");
  name.className = "tile__name";
  name.textContent = service.name;

  body.append(icon, name);

  const host = document.createElement("p");
  host.className = "tile__host";
  host.textContent = formatHostPort(service);

  const meta = document.createElement("div");
  meta.className = "tile__meta";

  const dot = document.createElement("span");
  dot.className = `dot dot--${statusTone(service.health)}`;
  dot.setAttribute("role", "img");
  dot.setAttribute("aria-label", statusDetail(service.health));
  dot.title = statusDetail(service.health);

  const status = document.createElement("span");
  status.className = "tile__status";
  status.setAttribute("aria-hidden", "true");
  status.textContent = statusLabel(service.health);
  status.title = statusDetail(service.health);

  const spacer = document.createElement("span");
  spacer.className = "tile__spacer";

  const open = document.createElement("a");
  open.className = "tile__action";
  open.href = service.url;
  open.target = "_blank";
  open.rel = "noopener noreferrer";
  open.textContent = "Open";
  open.title = `Open ${service.name} in a new tab`;

  const recheck = document.createElement("button");
  recheck.type = "button";
  recheck.className = "tile__action";
  recheck.dataset.checkService = String(service.id);
  recheck.textContent = "Recheck";
  recheck.title = `Probe ${service.name} now`;

  meta.append(dot, status, spacer, open, recheck);
  tile.append(body, host, meta);
  return tile;
}

export function renderGrid(groups) {
  const grid = document.getElementById("tile-grid");
  if (!grid) return;
  grid.replaceChildren();

  for (const group of groups) {
    const section = document.createElement("section");
    section.className = "group";
    section.dataset.categoryId = String(group.id);

    const head = document.createElement("div");
    head.className = "group__head";

    const title = document.createElement("h2");
    title.className = "group__title";
    title.id = `group-${group.id}`;
    title.textContent = group.name;

    const count = document.createElement("span");
    count.className = "group__count";
    count.dataset.count = "";
    count.textContent = String(group.services.length);

    head.append(title, count);
    section.setAttribute("aria-labelledby", title.id);

    const list = document.createElement("ul");
    list.className = "tiles";
    list.dataset.categoryId = String(group.id);
    for (const service of group.services) list.append(createTile(service));

    section.append(head, list);
    grid.append(section);
  }

  grid.hidden = groups.length === 0;
}

export function applyHealth(tile, health) {
  if (!tile) return;
  const dot = tile.querySelector(".dot");
  const status = tile.querySelector(".tile__status");
  if (dot) {
    dot.className = `dot dot--${statusTone(health)}`;
    dot.setAttribute("aria-label", statusDetail(health));
    dot.title = statusDetail(health);
  }
  if (status) {
    status.textContent = statusLabel(health);
    status.title = statusDetail(health);
  }
}
