import { fetchAndParseMarkdown, renderMarkdown } from "./markdown";
import { fetchJson } from "./fetch-json";
import { AtlasMap } from "./map-view";
import { buildRoute, parseRoute } from "./router";
import { pickLanguageValue } from "./i18n";
import { resolveRuntimePath } from "./runtime-path";
import type {
  AppData,
  FeatureFlags,
  GraphEdge,
  GraphNode,
  LanguageCode,
  LayersConfig,
  MapObjectsIndex,
  Manifest,
  NavigationConfig,
  ParsedMarkdownDocument,
  RouteState,
  SiteConfig,
  ThemeConfig,
  TimelineIndex
} from "./types";

export class AppController {
  private data!: AppData;
  private route!: RouteState;
  private map!: AtlasMap;
  private selectedYear: number | null = null;
  private root: HTMLElement;

  constructor(root: HTMLElement) {
    this.root = root;
  }

  async start(): Promise<void> {
    this.data = await this.loadData();
    this.route = parseRoute(location.hash, this.data.site.supportedLanguages, this.data.site.defaultLanguage);
    this.renderShell();
    this.map = new AtlasMap(this.query("#map"));
    this.map.onMarkerSelect((id) => {
      this.navigate({ language: this.route.language, view: "object", id });
    });
    await this.map.applyLayerConfig(this.data.layers);
    this.bindEvents();
    await this.renderCurrentRoute();
    this.map.invalidateSize();
  }

  private async loadData(): Promise<AppData> {
    const manifest = await fetchJson<Manifest>("data/manifest.json");
    const [site, navigation, layers, languages, theme, featureFlags, mapObjects, timeline, graphNodes, graphEdges] =
      await Promise.all([
        fetchJson<SiteConfig>("config/site.json"),
        fetchJson<NavigationConfig>("config/navigation.json"),
        fetchJson<LayersConfig>("config/layers.json"),
        fetchJson<AppData["languages"]>("config/languages.json"),
        fetchJson<ThemeConfig>("config/theme.json"),
        fetchJson<FeatureFlags>("config/feature-flags.json"),
        fetchJson<MapObjectsIndex>(manifest.indexes.mapObjects),
        fetchJson<TimelineIndex>(manifest.indexes.timeline),
        fetchJson<GraphNode[]>(manifest.indexes.graphNodes),
        fetchJson<GraphEdge[]>(manifest.indexes.graphEdges)
      ]);

    return {
      manifest,
      site,
      navigation,
      layers,
      languages,
      theme,
      featureFlags,
      mapObjects,
      timeline,
      graphNodes,
      graphEdges
    };
  }

  private renderShell(): void {
    this.root.innerHTML = `
      <div class="atlas-shell">
        <aside class="drawer drawer-menu" id="menu-drawer" aria-hidden="true"></aside>
        <aside class="drawer drawer-layers" id="layers-drawer" aria-hidden="true"></aside>
        <header class="topbar">
          <button class="icon-button" id="menu-toggle" aria-label="Open navigation menu">☰</button>
          <div class="topbar-titles">
            <a class="site-title" href="#/${this.route.language}/explore"></a>
            <p class="site-tagline"></p>
          </div>
          <div class="topbar-actions">
            <select id="language-select" aria-label="Select language"></select>
            <button class="icon-button" id="layers-toggle" aria-label="Open layer panel">◫</button>
          </div>
        </header>
        <main class="main-layout">
          <section class="map-stage" id="map-stage">
            <div class="map-frame" id="map"></div>
            <div class="timeline-panel" id="timeline-panel"></div>
          </section>
          <section class="content-panel" id="content-panel"></section>
        </main>
      </div>
    `;
    this.applyTheme();
    this.renderChrome();
  }

  private applyTheme(): void {
    Object.entries(this.data.theme.colors).forEach(([key, value]) => {
      document.documentElement.style.setProperty(`--${key}`, value);
    });
  }

  private renderChrome(): void {
    const title = pickLanguageValue(this.data.site.siteTitle, this.route.language).value;
    const tagline = pickLanguageValue(this.data.site.tagline, this.route.language).value;

    this.query(".site-title").textContent = title;
    this.query(".site-tagline").textContent = tagline;
    document.title = title;

    const languageSelect = this.query<HTMLSelectElement>("#language-select");
    languageSelect.innerHTML = this.data.site.supportedLanguages
      .map((language) => {
        const label = this.data.languages.labels[language];
        return `<option value="${language}" ${language === this.route.language ? "selected" : ""}>${label}</option>`;
      })
      .join("");

    this.renderMenuDrawer();
    this.renderLayersDrawer();
    this.renderTimeline();
  }

  private renderMenuDrawer(): void {
    const drawer = this.query("#menu-drawer");
    const navItems = this.data.navigation.main
      .map((item) => {
        const label = pickLanguageValue(item.label, this.route.language).value;
        if (item.type === "route") {
          return `<a class="drawer-link" href="${item.route?.replace("/en/", `/${this.route.language}/`) ?? "#"}">${label}</a>`;
        }
        if (item.type === "static_page") {
          return `<a class="drawer-link" href="#/${this.route.language}/page/${item.id}">${label}</a>`;
        }
        return `<a class="drawer-link" href="${item.url}" target="_blank" rel="noreferrer">${label} ↗</a>`;
      })
      .join("");

    drawer.innerHTML = `
      <div class="drawer-header">
        <h2>${pickLanguageValue(this.data.site.siteTitle, this.route.language).value}</h2>
        <p>${pickLanguageValue(this.data.site.tagline, this.route.language).value}</p>
      </div>
      <nav class="drawer-nav">${navItems}</nav>
      <a class="drawer-link drawer-muted" href="${this.data.site.repositoryUrl}" target="_blank" rel="noreferrer">GitHub ↗</a>
    `;
  }

  private renderLayersDrawer(): void {
    const drawer = this.query("#layers-drawer");
    const groupHtml = this.data.layers.groups
      .map((group) => {
        const label = pickLanguageValue(group.label, this.route.language).value;
        const layers = this.data.layers.layers
          .filter((layer) => layer.group === group.id)
          .map((layer) => {
            const layerLabel = pickLanguageValue(layer.label, this.route.language).value;
            const checked = layer.enabledByDefault ? "checked" : "";
            const disabled =
              layer.type === "google_map_tiles" || layer.type === "google_earth_3d_optional" ? "disabled" : "";
            const meta = [
              layer.attribution ? `<span>${layer.attribution}</span>` : "",
              layer.requiresNetwork ? "<span>External</span>" : "<span>Local</span>"
            ]
              .filter(Boolean)
              .join("");
            return `
              <label class="layer-row">
                <input data-layer-toggle="${layer.id}" type="checkbox" ${checked} ${disabled} />
                <span>
                  <strong>${layerLabel}</strong>
                  <small>${meta}</small>
                </span>
              </label>
            `;
          })
          .join("");
        return `<section class="layer-group"><h3>${label}</h3>${layers}</section>`;
      })
      .join("");

    drawer.innerHTML = `<div class="drawer-header"><h2>Layers</h2><p>Configuration-driven map layers</p></div>${groupHtml}`;
  }

  private renderTimeline(): void {
    const panel = this.query("#timeline-panel");
    const rangeStart = Number(this.data.timeline.range.from);
    const rangeEnd = this.data.timeline.range.to === "present" ? new Date().getFullYear() : Number(this.data.timeline.range.to);
    const selectedYear = this.selectedYear ?? 1850;

    panel.innerHTML = `
      <div class="timeline-topline">
        <strong>Timeline</strong>
        <span>${selectedYear}</span>
      </div>
      <input id="timeline-range" type="range" min="${rangeStart}" max="${rangeEnd}" step="1" value="${selectedYear}" />
      <div class="timeline-caption">Filter markers and time-aware objects by year.</div>
    `;
  }

  private bindEvents(): void {
    window.addEventListener("hashchange", async () => {
      this.route = parseRoute(location.hash, this.data.site.supportedLanguages, this.data.site.defaultLanguage);
      this.renderChrome();
      await this.renderCurrentRoute();
    });

    this.query("#menu-toggle").addEventListener("click", () => this.toggleDrawer("#menu-drawer"));
    this.query("#layers-toggle").addEventListener("click", () => this.toggleDrawer("#layers-drawer"));

    this.query<HTMLSelectElement>("#language-select").addEventListener("change", (event) => {
      const language = (event.target as HTMLSelectElement).value as LanguageCode;
      this.navigate({ ...this.route, language });
    });

    this.query("#timeline-panel").addEventListener("input", async (event) => {
      const target = event.target as HTMLInputElement;
      if (target.id === "timeline-range") {
        this.selectedYear = Number(target.value);
        this.renderTimeline();
        await this.renderCurrentRoute();
      }
    });

    this.query("#layers-drawer").addEventListener("change", async (event) => {
      const target = event.target as HTMLInputElement;
      const layerId = target.dataset.layerToggle;
      if (!layerId) {
        return;
      }
      const layer = this.data.layers.layers.find((entry) => entry.id === layerId);
      if (!layer) {
        return;
      }
      if (target.checked) {
        await this.map.enableLayer(layer);
      } else {
        this.map.disableLayer(layerId);
      }
    });
  }

  private async renderCurrentRoute(): Promise<void> {
    const visibleIds = this.getVisibleObjectIds();
    this.map.renderObjects(this.data.mapObjects, this.route.language, visibleIds);
    const panel = this.query("#content-panel");

    if (this.route.view === "object" && this.route.id) {
      const feature = this.data.mapObjects.features.find((entry) => entry.properties.id === this.route.id);
      if (feature) {
        const markdown = await fetchAndParseMarkdown(feature.properties.content_path);
        panel.innerHTML = this.renderObjectPanel(feature.properties, markdown);
        return;
      }
      const fallbackMarkdown = await this.tryContentFallback(this.route.id);
      if (fallbackMarkdown) {
        panel.innerHTML = this.renderGenericObjectPanel(fallbackMarkdown, this.route.id);
        return;
      }
      panel.innerHTML = this.renderMessage("Object not found", "The requested object is not present in the published index.");
      return;
    }

    if (this.route.view === "page" && this.route.id) {
      const navPage = this.data.navigation.main.find((item) => item.id === this.route.id);
      const contentPath = navPage?.contentPath ?? `content/pages/${this.route.id}.md`;
      const markdown = await fetchAndParseMarkdown(contentPath);
      panel.innerHTML = this.renderPagePanel(markdown);
      return;
    }

    if (this.route.view === "graph") {
      panel.innerHTML = this.renderGraphPanel();
      return;
    }

    if (this.route.view === "sources") {
      panel.innerHTML = this.renderSourcesPanel();
      return;
    }

    panel.innerHTML = this.renderExplorePanel(visibleIds.size);
  }

  private renderObjectPanel(properties: MapObjectsIndex["features"][number]["properties"], markdown: ParsedMarkdownDocument): string {
    const titleInfo = pickLanguageValue(properties.title, this.route.language);
    const summaryInfo = pickLanguageValue(properties.summary, this.route.language);
    const body = this.pickBody(markdown);
    const relations = Array.isArray(markdown.frontMatter.relations)
      ? (markdown.frontMatter.relations as Array<{ type: string; target: string }>)
      : [];
    const externalLinks = Array.isArray(markdown.frontMatter.external_links)
      ? (markdown.frontMatter.external_links as Array<{ label: string; url: string }>)
      : [];
    const languageNote = titleInfo.fallbackUsed || body.fallbackUsed ? `<p class="language-note">Selected language not available in full. Showing ${body.languageUsed ?? titleInfo.languageUsed ?? "fallback"} content.</p>` : "";
    const media = properties.media_preview
      ? `<img class="hero-image" src="${resolveRuntimePath(properties.media_preview)}" alt="${titleInfo.value}" />`
      : "";
    const relationList = relations
      .map((relation) => `<li>${relation.type}: <a href="#/${this.route.language}/object/${relation.target}">${relation.target}</a></li>`)
      .join("");
    const linkList = externalLinks
      .map((link) => `<li><a href="${link.url}" target="_blank" rel="noreferrer">${link.label} ↗</a></li>`)
      .join("");

    return `
      <article class="panel-article">
        <p class="eyebrow">${properties.category ?? properties.type}</p>
        <h1>${titleInfo.value}</h1>
        <p class="lede">${summaryInfo.value}</p>
        ${languageNote}
        ${media}
        <div class="meta-grid">
          <div><strong>Period</strong><span>${properties.time?.from ?? "Unknown"} - ${properties.time?.to ?? "Unknown"}</span></div>
          <div><strong>Certainty</strong><span>${properties.geometry_certainty ?? properties.time?.certainty ?? "unspecified"}</span></div>
          <div><strong>River relation</strong><span>${properties.river_relation?.distance_m ?? "?"} m</span></div>
          <div><strong>Graph</strong><a href="#/${this.route.language}/graph">Open graph view</a></div>
        </div>
        <div class="markdown-body">${renderMarkdown(body.value)}</div>
        <section class="related-section">
          <h2>Relations</h2>
          <ul>${relationList || "<li>No explicit relations in this sample object.</li>"}</ul>
        </section>
        <section class="related-section">
          <h2>External links</h2>
          <ul>${linkList || "<li>No external links.</li>"}</ul>
        </section>
      </article>
    `;
  }

  private renderPagePanel(markdown: ParsedMarkdownDocument): string {
    const titleInfo = pickLanguageValue(markdown.frontMatter.title as Record<string, string>, this.route.language);
    const body = this.pickBody(markdown);
    return `
      <article class="panel-article">
        <p class="eyebrow">Page</p>
        <h1>${titleInfo.value}</h1>
        ${body.fallbackUsed ? `<p class="language-note">Showing ${body.languageUsed ?? "fallback"} content.</p>` : ""}
        <div class="markdown-body">${renderMarkdown(body.value)}</div>
      </article>
    `;
  }

  private renderGenericObjectPanel(markdown: ParsedMarkdownDocument, id: string): string {
    const titleInfo = pickLanguageValue(markdown.frontMatter.title as Record<string, string>, this.route.language);
    const summaryInfo = pickLanguageValue(markdown.frontMatter.summary as Record<string, string>, this.route.language);
    const body = this.pickBody(markdown);
    return `
      <article class="panel-article">
        <p class="eyebrow">${String(markdown.frontMatter.type ?? "content")}</p>
        <h1>${titleInfo.value || id}</h1>
        <p class="lede">${summaryInfo.value}</p>
        ${body.fallbackUsed ? `<p class="language-note">Showing ${body.languageUsed ?? "fallback"} content.</p>` : ""}
        <div class="markdown-body">${renderMarkdown(body.value)}</div>
      </article>
    `;
  }

  private renderGraphPanel(): string {
    const nodes = this.data.graphNodes.slice(0, 8);
    const width = 420;
    const height = 260;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = 90;
    const positions = new Map<string, { x: number; y: number }>();
    nodes.forEach((node, index) => {
      const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
      positions.set(node.id, {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius
      });
    });
    const edges = this.data.graphEdges.filter((edge) => positions.has(edge.source) && positions.has(edge.target));

    const svgEdges = edges
      .map((edge) => {
        const source = positions.get(edge.source)!;
        const target = positions.get(edge.target)!;
        return `<line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" class="graph-edge" />`;
      })
      .join("");
    const svgNodes = nodes
      .map((node) => {
        const pos = positions.get(node.id)!;
        const label = pickLanguageValue(node.label, this.route.language).value;
        const className = node.kind === "external" ? "graph-node external" : "graph-node";
        const url = node.kind === "external" ? node.url : node.url.replace("/en/", `/${this.route.language}/`);
        return `<a href="${url}" ${node.kind === "external" ? 'target="_blank" rel="noreferrer"' : ""}>
          <circle class="${className}" cx="${pos.x}" cy="${pos.y}" r="16"></circle>
          <text x="${pos.x}" y="${pos.y + 32}" text-anchor="middle">${label}</text>
        </a>`;
      })
      .join("");

    const relationList = this.data.graphEdges
      .slice(0, 12)
      .map((edge) => `<li>${edge.source} → ${edge.type} → ${edge.target}</li>`)
      .join("");

    return `
      <article class="panel-article">
        <p class="eyebrow">Graph</p>
        <h1>Relationship graph</h1>
        <p class="lede">Static graph data loaded from JSON files.</p>
        <svg class="graph-svg" viewBox="0 0 ${width} ${height}" aria-label="Object relationship graph">${svgEdges}${svgNodes}</svg>
        <ul class="relation-list">${relationList}</ul>
      </article>
    `;
  }

  private renderSourcesPanel(): string {
    const items = this.data.mapObjects.features
      .map((feature) => {
        const title = pickLanguageValue(feature.properties.title, this.route.language).value;
        return `<li><a href="#/${this.route.language}/object/${feature.properties.id}">${title}</a> <span>${feature.properties.source_count ?? 0} sources</span></li>`;
      })
      .join("");
    return `
      <article class="panel-article">
        <p class="eyebrow">Sources</p>
        <h1>Source overview</h1>
        <p class="lede">Sample source counts generated into the published index.</p>
        <ul class="relation-list">${items}</ul>
      </article>
    `;
  }

  private renderExplorePanel(visibleCount: number): string {
    const year = this.selectedYear ?? 1850;
    const cards = this.data.mapObjects.features
      .filter((feature) => this.isVisibleInYear(feature.properties.id, year))
      .slice(0, 6)
      .map((feature) => {
        const title = pickLanguageValue(feature.properties.title, this.route.language).value;
        const summary = pickLanguageValue(feature.properties.summary, this.route.language).value;
        return `<a class="summary-card" href="#/${this.route.language}/object/${feature.properties.id}">
          <strong>${title}</strong>
          <span>${summary}</span>
        </a>`;
      })
      .join("");
    return `
      <article class="panel-article">
        <p class="eyebrow">Explore</p>
        <h1>Follow the river through time</h1>
        <p class="lede">The default public build runs from static config, GeoJSON, JSON, and Markdown files only.</p>
        <div class="meta-grid">
          <div><strong>Selected year</strong><span>${year}</span></div>
          <div><strong>Visible indexed objects</strong><span>${visibleCount}</span></div>
          <div><strong>Languages</strong><span>EN / DE / NL</span></div>
          <div><strong>Runtime</strong><span>Static client-side</span></div>
        </div>
        <div class="summary-card-grid">${cards}</div>
      </article>
    `;
  }

  private getVisibleObjectIds(): Set<string> {
    const year = this.selectedYear ?? 1850;
    return new Set(this.data.timeline.items.filter((item) => this.isVisibleInYear(item.id, year)).map((item) => item.id));
  }

  private isVisibleInYear(id: string, year: number): boolean {
    const item = this.data.timeline.items.find((entry) => entry.id === id);
    if (!item) {
      return true;
    }
    const from = item.from ? Number(item.from) : Number.NEGATIVE_INFINITY;
    const to = item.to ? Number(item.to) : Number.POSITIVE_INFINITY;
    return year >= from && year <= to;
  }

  private pickBody(markdown: ParsedMarkdownDocument): { value: string; fallbackUsed: boolean; languageUsed?: string } {
    if (markdown.bodyByLanguage[this.route.language]) {
      return { value: markdown.bodyByLanguage[this.route.language] ?? "", fallbackUsed: false, languageUsed: this.route.language };
    }
    for (const fallback of ["en", "nl", "de"] as const) {
      if (markdown.bodyByLanguage[fallback]) {
        return {
          value: markdown.bodyByLanguage[fallback] ?? "",
          fallbackUsed: fallback !== this.route.language,
          languageUsed: fallback
        };
      }
    }
    return { value: "", fallbackUsed: false };
  }

  private toggleDrawer(selector: string): void {
    const drawer = this.query(selector);
    const open = drawer.classList.toggle("is-open");
    drawer.setAttribute("aria-hidden", String(!open));
  }

  private navigate(route: RouteState): void {
    location.hash = buildRoute(route);
  }

  private renderMessage(title: string, body: string): string {
    return `<article class="panel-article"><h1>${title}</h1><p>${body}</p></article>`;
  }

  private async tryContentFallback(id: string): Promise<ParsedMarkdownDocument | null> {
    const candidates = [`content/stories/${id}.md`, `content/media/${id}.md`, `content/objects/${id}.md`];
    for (const candidate of candidates) {
      try {
        return await fetchAndParseMarkdown(candidate);
      } catch {
        continue;
      }
    }
    return null;
  }

  private query<T extends HTMLElement = HTMLElement>(selector: string): T {
    const element = this.root.querySelector<T>(selector);
    if (!element) {
      throw new Error(`Missing element for selector ${selector}`);
    }
    return element;
  }
}
