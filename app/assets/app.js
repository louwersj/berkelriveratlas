const state = {
  data: null,
  route: null,
  selectedYear: 1850,
  activeLayers: new Set(),
  layerCache: new Map()
};

const LANGUAGE_FALLBACK = ["en", "nl", "de"];

start().catch((error) => {
  console.error(error);
  document.querySelector("#app").innerHTML = `<main class="panel-article"><h1>Application failed to start</h1><p>${String(error)}</p></main>`;
});

async function start() {
  state.data = await loadData();
  state.route = parseRoute(location.hash, state.data.site.supportedLanguages, state.data.site.defaultLanguage);
  renderShell();
  bindEvents();
  await ensureDefaultLayersLoaded();
  await renderRoute();
}

async function loadData() {
  const manifest = await fetchJson("data/manifest.json");
  const [site, navigation, languages, theme, featureFlags, mapObjects, timeline, graphNodes, graphEdges, layers] =
    await Promise.all([
      fetchJson("config/site.json"),
      fetchJson("config/navigation.json"),
      fetchJson("config/languages.json"),
      fetchJson("config/theme.json"),
      fetchJson("config/feature-flags.json"),
      fetchJson(manifest.indexes.mapObjects),
      fetchJson(manifest.indexes.timeline),
      fetchJson(manifest.indexes.graphNodes),
      fetchJson(manifest.indexes.graphEdges),
      fetchJson("config/layers.json")
    ]);

  return {
    manifest,
    site,
    navigation,
    languages,
    theme,
    featureFlags,
    mapObjects,
    timeline,
    graphNodes,
    graphEdges,
    layers
  };
}

function renderShell() {
  const root = document.querySelector("#app");
  root.innerHTML = `
    <div class="atlas-shell">
      <aside class="drawer drawer-menu" id="menu-drawer" aria-hidden="true"></aside>
      <aside class="drawer drawer-layers" id="layers-drawer" aria-hidden="true"></aside>
      <header class="topbar">
        <button class="icon-button" id="menu-toggle" aria-label="Open navigation menu">☰</button>
        <div class="topbar-titles">
          <a class="site-title" id="site-title-link" href="#/${state.route.language}/explore"></a>
          <p class="site-tagline" id="site-tagline"></p>
        </div>
        <div class="topbar-actions">
          <select id="language-select" aria-label="Select language"></select>
          <button class="icon-button" id="layers-toggle" aria-label="Open layer panel">◫</button>
        </div>
      </header>
      <main class="main-layout">
        <section class="map-stage">
          <div class="map-frame" id="map"></div>
          <div class="timeline-panel" id="timeline-panel"></div>
        </section>
        <section class="content-panel" id="content-panel"></section>
      </main>
    </div>
  `;

  applyTheme();
  renderChrome();
}

function applyTheme() {
  Object.entries(state.data.theme.colors).forEach(([key, value]) => {
    document.documentElement.style.setProperty(`--${key}`, value);
  });
}

function renderChrome() {
  const title = pickLanguageValue(state.data.site.siteTitle, state.route.language).value;
  const tagline = pickLanguageValue(state.data.site.tagline, state.route.language).value;
  document.title = title;
  document.querySelector("#site-title-link").textContent = title;
  document.querySelector("#site-tagline").textContent = tagline;

  const languageSelect = document.querySelector("#language-select");
  languageSelect.innerHTML = state.data.site.supportedLanguages
    .map((language) => `<option value="${language}" ${language === state.route.language ? "selected" : ""}>${state.data.languages.labels[language]}</option>`)
    .join("");

  renderMenuDrawer();
  renderLayersDrawer();
  renderTimeline();
}

function renderMenuDrawer() {
  const drawer = document.querySelector("#menu-drawer");
  drawer.innerHTML = `
    <div class="drawer-header">
      <h2>${pickLanguageValue(state.data.site.siteTitle, state.route.language).value}</h2>
      <p>${pickLanguageValue(state.data.site.tagline, state.route.language).value}</p>
    </div>
    <nav class="drawer-nav">
      ${state.data.navigation.main
        .map((item) => {
          const label = pickLanguageValue(item.label, state.route.language).value;
          if (item.type === "route") {
            return `<a class="drawer-link" href="${item.route.replace("/en/", `/${state.route.language}/`)}">${label}</a>`;
          }
          if (item.type === "static_page") {
            return `<a class="drawer-link" href="#/${state.route.language}/page/${item.id}">${label}</a>`;
          }
          return `<a class="drawer-link" href="${item.url}" target="_blank" rel="noreferrer">${label} ↗</a>`;
        })
        .join("")}
    </nav>
  `;
}

function renderLayersDrawer() {
  const drawer = document.querySelector("#layers-drawer");
  drawer.innerHTML = `
    <div class="drawer-header">
      <h2>Layers</h2>
      <p>Configuration-driven layer control</p>
    </div>
    ${state.data.layers.groups
      .map((group) => {
        const label = pickLanguageValue(group.label, state.route.language).value;
        const rows = state.data.layers.layers
          .filter((layer) => layer.group === group.id)
          .map((layer) => {
            const checked = state.activeLayers.has(layer.id) ? "checked" : "";
            const disabled = ["google_map_tiles", "google_earth_3d_optional"].includes(layer.type) ? "disabled" : "";
            const layerLabel = pickLanguageValue(layer.label, state.route.language).value;
            return `
              <label class="layer-row">
                <input type="checkbox" data-layer-toggle="${layer.id}" ${checked} ${disabled} />
                <span>
                  <strong>${layerLabel}</strong>
                  <small>${layer.attribution || ""} ${layer.requiresNetwork ? "External" : "Local"}</small>
                </span>
              </label>
            `;
          })
          .join("");
        return `<section class="layer-group"><h3>${label}</h3>${rows}</section>`;
      })
      .join("")}
  `;
}

function renderTimeline() {
  const panel = document.querySelector("#timeline-panel");
  const from = Number(state.data.timeline.range.from);
  const to = state.data.timeline.range.to === "present" ? new Date().getFullYear() : Number(state.data.timeline.range.to);
  panel.innerHTML = `
    <div class="timeline-topline">
      <strong>Timeline</strong>
      <span>${state.selectedYear}</span>
    </div>
    <input id="timeline-range" type="range" min="${from}" max="${to}" step="1" value="${state.selectedYear}" />
    <div class="timeline-caption">Filter markers and time-aware objects by year.</div>
  `;
}

async function ensureDefaultLayersLoaded() {
  for (const layer of state.data.layers.layers) {
    if (layer.enabledByDefault) {
      state.activeLayers.add(layer.id);
      await ensureLayerData(layer);
    }
  }
}

async function ensureLayerData(layer) {
  if (!layer.url || state.layerCache.has(layer.id) || layer.type !== "geojson") {
    return;
  }
  const geojson = await fetchJson(layer.url);
  state.layerCache.set(layer.id, geojson);
}

function bindEvents() {
  window.addEventListener("hashchange", async () => {
    state.route = parseRoute(location.hash, state.data.site.supportedLanguages, state.data.site.defaultLanguage);
    renderChrome();
    await renderRoute();
  });

  document.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    if (target.id === "menu-toggle") {
      toggleDrawer("#menu-drawer");
    }

    if (target.id === "layers-toggle") {
      toggleDrawer("#layers-drawer");
    }

    const markerId = target.dataset.markerId;
    const markerTarget = markerId ? target : target.closest("[data-marker-id]");
    if (markerTarget && markerTarget.dataset.markerId) {
      location.hash = `#/${state.route.language}/object/${markerTarget.dataset.markerId}`;
    }
  });

  document.addEventListener("change", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    if (target.id === "language-select") {
      const language = target.value;
      location.hash = buildRoute({ ...state.route, language });
    }

    if (target.dataset.layerToggle) {
      const layer = state.data.layers.layers.find((entry) => entry.id === target.dataset.layerToggle);
      if (!layer) {
        return;
      }
      if (target.checked) {
        state.activeLayers.add(layer.id);
        await ensureLayerData(layer);
      } else {
        state.activeLayers.delete(layer.id);
      }
      renderLayersDrawer();
      renderMap();
    }
  });

  document.addEventListener("input", async (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement && target.id === "timeline-range") {
      state.selectedYear = Number(target.value);
      renderTimeline();
      await renderRoute();
    }
  });
}

async function renderRoute() {
  renderMap();
  const panel = document.querySelector("#content-panel");
  const visibleIds = getVisibleIds();

  if (state.route.view === "object" && state.route.id) {
    const feature = state.data.mapObjects.features.find((entry) => entry.properties.id === state.route.id);
    if (feature) {
      const markdown = await fetchAndParseMarkdown(feature.properties.content_path);
      panel.innerHTML = renderObjectPanel(feature.properties, markdown);
      return;
    }
    const fallback = await tryContentFallback(state.route.id);
    if (fallback) {
      panel.innerHTML = renderGenericPanel(fallback, state.route.id);
      return;
    }
  }

  if (state.route.view === "page" && state.route.id) {
    const navPage = state.data.navigation.main.find((item) => item.id === state.route.id);
    const path = navPage?.contentPath || `content/pages/${state.route.id}.md`;
    const markdown = await fetchAndParseMarkdown(path);
    panel.innerHTML = renderPagePanel(markdown);
    return;
  }

  if (state.route.view === "graph") {
    panel.innerHTML = renderGraphPanel();
    return;
  }

  if (state.route.view === "sources") {
    panel.innerHTML = renderSourcesPanel();
    return;
  }

  panel.innerHTML = renderExplorePanel(visibleIds.size);
}

function renderMap() {
  const container = document.querySelector("#map");
  const features = state.data.mapObjects.features.filter((feature) => getVisibleIds().has(feature.properties.id));
  const layerDefs = state.data.layers.layers.filter((layer) => state.activeLayers.has(layer.id));
  const layerFeatures = [];

  layerDefs.forEach((layer) => {
    const geojson = state.layerCache.get(layer.id);
    if (geojson && Array.isArray(geojson.features)) {
      geojson.features.forEach((feature) => {
        layerFeatures.push({ feature, layer });
      });
    }
  });

  const bounds = computeBounds([
    ...features.map((feature) => feature.geometry),
    ...layerFeatures.map((entry) => entry.feature.geometry)
  ]);
  const width = 1000;
  const height = 700;
  const padding = 48;

  const layerSvg = layerFeatures
    .map(({ feature, layer }) => renderGeometry(feature.geometry, bounds, width, height, padding, layer.style || {}, layer.type))
    .join("");

  const objectSvg = features
    .map((feature) => renderObjectFeature(feature, bounds, width, height, padding))
    .join("");

  container.innerHTML = `
    <svg class="map-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Berkel atlas map">
      <rect width="${width}" height="${height}" fill="rgba(221,231,234,0.35)"></rect>
      ${layerSvg}
      ${objectSvg}
      <text x="40" y="${height - 30}" fill="#66665f" font-size="18">Static sample atlas map</text>
    </svg>
  `;
}

function renderObjectFeature(feature, bounds, width, height, padding) {
  const props = feature.properties;
  const title = pickLanguageValue(props.title, state.route.language).value;
  const category = props.category || props.type;
  if (feature.geometry.type === "Point") {
    const [x, y] = projectPoint(feature.geometry.coordinates, bounds, width, height, padding);
    const fill = category.includes("map") || category.includes("image") ? "#C9821E" : "#faf8f1";
    return `
      <g>
        <circle cx="${x}" cy="${y}" r="${category.includes("image") ? 6 : 5}" fill="${fill}" stroke="#30302D" stroke-width="1.5" data-marker-id="${props.id}"></circle>
        <title>${title}</title>
      </g>
    `;
  }
  const path = renderGeometry(feature.geometry, bounds, width, height, padding, { stroke: "#8E1B5B", strokeWidth: 2, strokeOpacity: 0.9, fill: "#8E1B5B", fillOpacity: 0.06 }, "geojson");
  return `<g data-marker-id="${props.id}">${path}<title>${title}</title></g>`;
}

function renderGeometry(geometry, bounds, width, height, padding, style, type) {
  if (geometry.type === "LineString") {
    const points = geometry.coordinates.map((coords) => projectPoint(coords, bounds, width, height, padding).join(",")).join(" ");
    return `<polyline points="${points}" fill="none" stroke="${style.stroke || "#30302D"}" stroke-width="${style.strokeWidth || 1}" stroke-opacity="${style.strokeOpacity ?? 1}" stroke-dasharray="${style.dashArray || ""}"></polyline>`;
  }
  if (geometry.type === "Polygon") {
    const rings = geometry.coordinates
      .map((ring) => ring.map((coords) => projectPoint(coords, bounds, width, height, padding).join(",")).join(" "))
      .map((points) => `<polygon points="${points}" fill="${style.fill || style.stroke || "#30302D"}" fill-opacity="${style.fillOpacity ?? 0.08}" stroke="${style.stroke || "#30302D"}" stroke-width="${style.strokeWidth || 1}" stroke-opacity="${style.strokeOpacity ?? 1}" stroke-dasharray="${style.dashArray || ""}"></polygon>`)
      .join("");
    return rings;
  }
  if (geometry.type === "Point") {
    const [x, y] = projectPoint(geometry.coordinates, bounds, width, height, padding);
    return `<circle cx="${x}" cy="${y}" r="4" fill="${style.fill || "#faf8f1"}" stroke="${style.stroke || "#30302D"}" stroke-width="${style.strokeWidth || 1}"></circle>`;
  }
  return "";
}

function computeBounds(geometries) {
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  geometries.forEach((geometry) => walkCoordinates(geometry.coordinates, (lon, lat) => {
    minLon = Math.min(minLon, lon);
    minLat = Math.min(minLat, lat);
    maxLon = Math.max(maxLon, lon);
    maxLat = Math.max(maxLat, lat);
  }));
  return { minLon, minLat, maxLon, maxLat };
}

function walkCoordinates(coords, callback) {
  if (typeof coords[0] === "number") {
    callback(coords[0], coords[1]);
    return;
  }
  coords.forEach((child) => walkCoordinates(child, callback));
}

function projectPoint(coords, bounds, width, height, padding) {
  const lon = coords[0];
  const lat = coords[1];
  const x = padding + ((lon - bounds.minLon) / Math.max(bounds.maxLon - bounds.minLon, 0.0001)) * (width - padding * 2);
  const y = height - padding - ((lat - bounds.minLat) / Math.max(bounds.maxLat - bounds.minLat, 0.0001)) * (height - padding * 2);
  return [x, y];
}

function renderExplorePanel(visibleCount) {
  const cards = state.data.mapObjects.features
    .filter((feature) => getVisibleIds().has(feature.properties.id))
    .slice(0, 6)
    .map((feature) => {
      const title = pickLanguageValue(feature.properties.title, state.route.language).value;
      const summary = pickLanguageValue(feature.properties.summary, state.route.language).value;
      return `<a class="summary-card" href="#/${state.route.language}/object/${feature.properties.id}"><strong>${title}</strong><span>${summary}</span></a>`;
    })
    .join("");

  return `
    <article class="panel-article">
      <p class="eyebrow">Explore</p>
      <h1>Follow the river through time</h1>
      <p class="lede">The public default build is fully static and runs from Markdown, GeoJSON, JSON, and local media files.</p>
      <div class="meta-grid">
        <div><strong>Selected year</strong><span>${state.selectedYear}</span></div>
        <div><strong>Visible indexed objects</strong><span>${visibleCount}</span></div>
        <div><strong>Languages</strong><span>EN / DE / NL</span></div>
        <div><strong>Runtime</strong><span>Static client-side</span></div>
      </div>
      <div class="summary-card-grid">${cards}</div>
    </article>
  `;
}

function renderObjectPanel(properties, markdown) {
  const titleInfo = pickLanguageValue(properties.title, state.route.language);
  const summaryInfo = pickLanguageValue(properties.summary, state.route.language);
  const body = pickBody(markdown);
  const relations = Array.isArray(markdown.frontMatter.relations) ? markdown.frontMatter.relations : [];
  const externalLinks = Array.isArray(markdown.frontMatter.external_links) ? markdown.frontMatter.external_links : [];
  const media = properties.media_preview ? `<img class="hero-image" src="${resolvePath(properties.media_preview)}" alt="${titleInfo.value}" />` : "";
  return `
    <article class="panel-article">
      <p class="eyebrow">${properties.category || properties.type}</p>
      <h1>${titleInfo.value}</h1>
      <p class="lede">${summaryInfo.value}</p>
      ${titleInfo.fallbackUsed || body.fallbackUsed ? `<p class="language-note">Showing ${body.languageUsed || titleInfo.languageUsed || "fallback"} content.</p>` : ""}
      ${media}
      <div class="meta-grid">
        <div><strong>Period</strong><span>${properties.time?.from || "Unknown"} - ${properties.time?.to || "Unknown"}</span></div>
        <div><strong>Certainty</strong><span>${properties.geometry_certainty || properties.time?.certainty || "unspecified"}</span></div>
        <div><strong>River relation</strong><span>${properties.river_relation?.distance_m ?? "?"} m</span></div>
        <div><strong>Graph</strong><a href="#/${state.route.language}/graph">Open graph view</a></div>
      </div>
      <div class="markdown-body">${markdownToHtml(body.value)}</div>
      <section class="related-section">
        <h2>Relations</h2>
        <ul>${relations.map((relation) => `<li>${relation.type}: <a href="#/${state.route.language}/object/${relation.target}">${relation.target}</a></li>`).join("") || "<li>No explicit relations in this sample object.</li>"}</ul>
      </section>
      <section class="related-section">
        <h2>External links</h2>
        <ul>${externalLinks.map((link) => `<li><a href="${link.url}" target="_blank" rel="noreferrer">${link.label} ↗</a></li>`).join("") || "<li>No external links.</li>"}</ul>
      </section>
    </article>
  `;
}

function renderPagePanel(markdown) {
  const titleInfo = pickLanguageValue(markdown.frontMatter.title, state.route.language);
  const body = pickBody(markdown);
  return `
    <article class="panel-article">
      <p class="eyebrow">Page</p>
      <h1>${titleInfo.value}</h1>
      ${body.fallbackUsed ? `<p class="language-note">Showing ${body.languageUsed || "fallback"} content.</p>` : ""}
      <div class="markdown-body">${markdownToHtml(body.value)}</div>
    </article>
  `;
}

function renderGenericPanel(markdown, id) {
  const titleInfo = pickLanguageValue(markdown.frontMatter.title || {}, state.route.language);
  const summaryInfo = pickLanguageValue(markdown.frontMatter.summary || {}, state.route.language);
  const body = pickBody(markdown);
  return `
    <article class="panel-article">
      <p class="eyebrow">${markdown.frontMatter.type || "content"}</p>
      <h1>${titleInfo.value || id}</h1>
      <p class="lede">${summaryInfo.value || ""}</p>
      <div class="markdown-body">${markdownToHtml(body.value)}</div>
    </article>
  `;
}

function renderGraphPanel() {
  const nodes = state.data.graphNodes.slice(0, 10);
  const width = 420;
  const height = 260;
  const radius = 90;
  const centerX = width / 2;
  const centerY = height / 2;
  const positions = new Map();
  nodes.forEach((node, index) => {
    const angle = (index / nodes.length) * Math.PI * 2;
    positions.set(node.id, {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius
    });
  });
  const edges = state.data.graphEdges.filter((edge) => positions.has(edge.source) && positions.has(edge.target));
  return `
    <article class="panel-article">
      <p class="eyebrow">Graph</p>
      <h1>Relationship graph</h1>
      <p class="lede">Static graph data loaded from JSON files.</p>
      <svg class="graph-svg" viewBox="0 0 ${width} ${height}">
        ${edges.map((edge) => {
          const source = positions.get(edge.source);
          const target = positions.get(edge.target);
          return `<line class="graph-edge" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}"></line>`;
        }).join("")}
        ${nodes.map((node) => {
          const pos = positions.get(node.id);
          const label = pickLanguageValue(node.label, state.route.language).value;
          const className = node.kind === "external" ? "graph-node external" : "graph-node";
          const href = node.kind === "external" ? node.url : node.url.replace("/en/", `/${state.route.language}/`);
          return `
            <a href="${href}" ${node.kind === "external" ? 'target="_blank" rel="noreferrer"' : ""}>
              <circle class="${className}" cx="${pos.x}" cy="${pos.y}" r="16"></circle>
              <text x="${pos.x}" y="${pos.y + 30}" text-anchor="middle" font-size="11">${label}</text>
            </a>
          `;
        }).join("")}
      </svg>
      <ul class="relation-list">${state.data.graphEdges.slice(0, 12).map((edge) => `<li>${edge.source} → ${edge.type} → ${edge.target}</li>`).join("")}</ul>
    </article>
  `;
}

function renderSourcesPanel() {
  return `
    <article class="panel-article">
      <p class="eyebrow">Sources</p>
      <h1>Source overview</h1>
      <p class="lede">Sample source counts generated into the published index.</p>
      <ul class="relation-list">${state.data.mapObjects.features.map((feature) => `<li><a href="#/${state.route.language}/object/${feature.properties.id}">${pickLanguageValue(feature.properties.title, state.route.language).value}</a> <span>${feature.properties.source_count || 0} sources</span></li>`).join("")}</ul>
    </article>
  `;
}

function getVisibleIds() {
  return new Set(
    state.data.timeline.items
      .filter((item) => {
        const from = parseYear(item.from);
        const to = parseYear(item.to);
        const year = state.selectedYear;
        return (from === null || year >= from) && (to === null || year <= to);
      })
      .map((item) => item.id)
  );
}

async function tryContentFallback(id) {
  const candidates = [`content/stories/${id}.md`, `content/media/${id}.md`, `content/objects/${id}.md`, `content/pages/${id}.md`];
  for (const candidate of candidates) {
    try {
      return await fetchAndParseMarkdown(candidate);
    } catch {
      continue;
    }
  }
  return null;
}

function parseRoute(hash, supportedLanguages, defaultLanguage) {
  const clean = hash.replace(/^#\/?/, "");
  if (!clean) {
    return { language: defaultLanguage, view: "explore" };
  }
  const [languageRaw, viewRaw, ...rest] = clean.split("/");
  const language = supportedLanguages.includes(languageRaw) ? languageRaw : defaultLanguage;
  const view = ["object", "page", "graph", "sources"].includes(viewRaw) ? viewRaw : "explore";
  return { language, view, id: rest.join("/") || undefined };
}

function buildRoute(route) {
  if (route.view === "explore") {
    return `#/${route.language}/explore`;
  }
  return `#/${route.language}/${route.view}${route.id ? `/${route.id}` : ""}`;
}

function toggleDrawer(selector) {
  const drawer = document.querySelector(selector);
  const open = drawer.classList.toggle("is-open");
  drawer.setAttribute("aria-hidden", String(!open));
}

function parseYear(value) {
  if (!value || value === "unknown") {
    return null;
  }
  if (value === "present") {
    return new Date().getFullYear();
  }
  const parsed = Number(String(value).slice(0, 4));
  return Number.isFinite(parsed) ? parsed : null;
}

function resolvePath(path) {
  if (/^https?:\/\//.test(path) || path.startsWith("#")) {
    return path;
  }
  return `./${path.replace(/^\.?\//, "")}`;
}

async function fetchJson(path) {
  const response = await fetch(resolvePath(path));
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}`);
  }
  return response.json();
}

async function fetchText(path) {
  const response = await fetch(resolvePath(path));
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}`);
  }
  return response.text();
}

async function fetchAndParseMarkdown(path) {
  const text = await fetchText(path);
  return parseMarkdown(text);
}

function parseMarkdown(text) {
  const match = text.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!match) {
    return { frontMatter: {}, bodyByLanguage: { en: text } };
  }
  const frontMatter = JSON.parse(match[1]);
  return {
    frontMatter,
    bodyByLanguage: splitBodyByLanguage(match[2])
  };
}

function splitBodyByLanguage(body) {
  const regex = /^##\s+(en|de|nl)\s*$/gm;
  const matches = [...body.matchAll(regex)];
  if (matches.length === 0) {
    return { en: body.trim() };
  }
  const output = {};
  for (let index = 0; index < matches.length; index += 1) {
    const current = matches[index];
    const start = current.index + current[0].length;
    const end = index + 1 < matches.length ? matches[index + 1].index : body.length;
    output[current[1]] = body.slice(start, end).trim();
  }
  return output;
}

function pickBody(markdown) {
  if (markdown.bodyByLanguage[state.route.language]) {
    return { value: markdown.bodyByLanguage[state.route.language], fallbackUsed: false, languageUsed: state.route.language };
  }
  for (const language of LANGUAGE_FALLBACK) {
    if (markdown.bodyByLanguage[language]) {
      return { value: markdown.bodyByLanguage[language], fallbackUsed: language !== state.route.language, languageUsed: language };
    }
  }
  return { value: "", fallbackUsed: false };
}

function pickLanguageValue(map, language) {
  if (!map) {
    return { value: "", fallbackUsed: false };
  }
  if (map[language]) {
    return { value: map[language], fallbackUsed: false, languageUsed: language };
  }
  for (const fallback of LANGUAGE_FALLBACK) {
    if (map[fallback]) {
      return { value: map[fallback], fallbackUsed: fallback !== language, languageUsed: fallback };
    }
  }
  const first = Object.entries(map).find((entry) => entry[1]);
  return { value: first ? first[1] : "", fallbackUsed: Boolean(first), languageUsed: first ? first[0] : undefined };
}

function markdownToHtml(markdown) {
  const blocks = markdown.trim().split(/\n\s*\n/);
  return blocks
    .map((block) => {
      if (block.startsWith("- ")) {
        const items = block.split("\n").map((line) => `<li>${inlineMarkdown(line.replace(/^- /, ""))}</li>`).join("");
        return `<ul>${items}</ul>`;
      }
      if (block.startsWith("### ")) {
        return `<h3>${inlineMarkdown(block.slice(4))}</h3>`;
      }
      if (block.startsWith("## ")) {
        return `<h2>${inlineMarkdown(block.slice(3))}</h2>`;
      }
      return `<p>${inlineMarkdown(block.replace(/\n/g, "<br>"))}</p>`;
    })
    .join("");
}

function inlineMarkdown(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2">$1</a>');
}
