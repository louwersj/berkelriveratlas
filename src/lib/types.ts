export type LanguageCode = "en" | "de" | "nl";

export interface LanguageMap {
  en?: string;
  de?: string;
  nl?: string;
  [key: string]: string | undefined;
}

export interface SiteConfig {
  siteTitle: LanguageMap;
  shortTitle: LanguageMap;
  tagline: LanguageMap;
  defaultLanguage: LanguageCode;
  supportedLanguages: LanguageCode[];
  dataBaseUrl: string;
  contentBaseUrl: string;
  repositoryUrl: string;
}

export interface NavItem {
  id: string;
  type: "route" | "static_page" | "external_link";
  label: LanguageMap;
  route?: string;
  contentPath?: string;
  url?: string;
  openInNewTab?: boolean;
}

export interface NavigationConfig {
  main: NavItem[];
}

export interface ThemeConfig {
  colors: Record<string, string>;
}

export interface FeatureFlags {
  graphPage: boolean;
  sourcesPage: boolean;
  historicOverlays: boolean;
}

export interface LanguagesConfig {
  supported: LanguageCode[];
  labels: Record<LanguageCode, string>;
}

export interface LayerGroup {
  id: string;
  label: LanguageMap;
}

export interface LayerDefinition {
  id: string;
  group: string;
  type:
    | "geojson"
    | "xyz_tile"
    | "wmts_tile"
    | "wms_tile"
    | "local_raster_tile"
    | "historic_overlay"
    | "image_bounds"
    | "google_map_tiles"
    | "google_earth_3d_optional"
    | "external_historic_tile";
  role?: "base" | "overlay";
  enabledByDefault?: boolean;
  label: LanguageMap;
  url?: string;
  manifestUrl?: string;
  tileManifestUrl?: string;
  attribution?: string;
  opacity?: number;
  provider?: string;
  year?: number;
  requiresNetwork?: boolean;
  requiresApiKey?: boolean;
  requiresBilling?: boolean;
  allowInPublicDefaultBuild?: boolean;
  documentation?: string;
  mapType?: string;
  style?: {
    stroke?: string;
    strokeWidth?: number;
    strokeOpacity?: number;
    fill?: string;
    fillOpacity?: number;
    dashArray?: string;
  };
  time?: {
    from: string;
    to: string;
    mode?: string;
  };
}

export interface GeoJsonChunkDescriptor {
  url: string;
  featureCount: number;
  bytes: number;
}

export interface GeoJsonBundleManifest {
  type: "geojson_bundle";
  generatedAt: string;
  layerId: string;
  featureCount: number;
  chunkCount: number;
  chunkSizeLimitBytes: number;
  chunks: GeoJsonChunkDescriptor[];
}

export interface GeoJsonTileDescriptor {
  id: string;
  row: number;
  col: number;
  bbox: [number, number, number, number];
  url: string;
  featureCount: number;
  bytes: number;
}

export interface GeoJsonTileManifest {
  type: "geojson_tile_set";
  generatedAt: string;
  layerId: string;
  featureCount: number;
  tileGrid: [number, number];
  bbox: [number, number, number, number];
  tiles: GeoJsonTileDescriptor[];
}

export interface LayersConfig {
  version: string;
  defaultBaseLayer: string;
  groups: LayerGroup[];
  layers: LayerDefinition[];
}

export interface Manifest {
  generated_at: string;
  data_base_url: string;
  github_raw_base_url?: string;
  prefer_local_data: boolean;
  config: string[];
  indexes: Record<string, string>;
}

export interface TimelineItem {
  id: string;
  content_path: string;
  type: string;
  category?: string;
  from?: string;
  to?: string;
  certainty?: string;
  title: LanguageMap;
  geometry_id?: string;
}

export interface TimelineIndex {
  generated_at: string;
  range: {
    from: string;
    to: string;
  };
  items: TimelineItem[];
}

export interface GraphNode {
  id: string;
  kind: "internal" | "external";
  type: string;
  category?: string;
  label: LanguageMap;
  url: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GeoFeatureProperties {
  id: string;
  type: string;
  category?: string;
  content_path: string;
  title: LanguageMap;
  summary: LanguageMap;
  time?: {
    from?: string;
    to?: string;
    certainty?: string;
  };
  river_relation?: {
    course?: string[];
    distance_m?: number;
    side?: string;
  };
  tags?: string[];
  media_preview?: string;
  source_count?: number;
  language_available?: string[];
  graph_node_id?: string;
  geometry_certainty?: string;
}

export interface MapObjectsIndex extends GeoJSON.FeatureCollection {
  generated_at: string;
  features: Array<GeoJSON.Feature<GeoJSON.Geometry, GeoFeatureProperties>>;
}

export interface ParsedMarkdownDocument {
  frontMatter: Record<string, unknown>;
  bodyByLanguage: Partial<Record<LanguageCode, string>>;
}

export interface ObjectSummary {
  id: string;
  title: LanguageMap;
  summary: LanguageMap;
  contentPath: string;
}

export interface AppData {
  manifest: Manifest;
  site: SiteConfig;
  navigation: NavigationConfig;
  layers: LayersConfig;
  languages: LanguagesConfig;
  theme: ThemeConfig;
  featureFlags: FeatureFlags;
  mapObjects: MapObjectsIndex;
  timeline: TimelineIndex;
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
}

export interface RouteState {
  language: LanguageCode;
  view: "explore" | "object" | "page" | "graph" | "sources";
  id?: string;
}
