import L from "leaflet";
import type {
  GeoFeatureProperties,
  GeoJsonBundleManifest,
  GeoJsonTileManifest,
  LanguageCode,
  LayerDefinition,
  LayersConfig,
  MapObjectsIndex,
} from "./types";
import { pickLanguageValue } from "./i18n";
import { resolveRuntimePath } from "./runtime-path";

type LayerInstance = L.Layer | null;
type TileCacheEntry = {
  manifest: GeoJsonTileManifest;
  tiles: Map<string, GeoJSON.FeatureCollection>;
  layer: L.GeoJSON<GeoJSON.Geometry>;
};

export class AtlasMap {
  private map: L.Map;
  private activeLayers = new Map<string, LayerInstance>();
  private tiledLayers = new Map<string, TileCacheEntry>();
  private featureLayer: L.GeoJSON<GeoJSON.Geometry, GeoFeatureProperties> | null = null;
  private markerHandler: ((featureId: string) => void) | null = null;

  constructor(container: HTMLElement) {
    this.map = L.map(container, {
      zoomControl: false,
      attributionControl: true
    }).setView([52.08, 6.54], 11);
    L.control.zoom({ position: "bottomright" }).addTo(this.map);
    this.map.on("moveend", () => {
      void this.refreshVisibleTiles();
    });
  }

  async applyLayerConfig(layersConfig: LayersConfig): Promise<void> {
    for (const layer of layersConfig.layers) {
      if (layer.enabledByDefault) {
        await this.enableLayer(layer);
      }
    }
  }

  async enableLayer(layer: LayerDefinition): Promise<void> {
    if (this.activeLayers.has(layer.id)) {
      return;
    }

    let instance: LayerInstance = null;
    if (layer.type === "geojson" && layer.tileManifestUrl) {
      const tileEntry = await createTiledLayer(layer, this.map);
      instance = tileEntry.layer;
      this.tiledLayers.set(layer.id, tileEntry);
    } else if (layer.type === "geojson" && (layer.url || layer.manifestUrl)) {
      const data = await loadGeoJsonLayer(layer);
      instance = L.geoJSON(data, {
        style: () => ({
          color: layer.style?.stroke ?? "#30302D",
          weight: layer.style?.strokeWidth ?? 1,
          opacity: layer.style?.strokeOpacity ?? 1,
          fillColor: layer.style?.fill ?? layer.style?.stroke ?? "#30302D",
          fillOpacity: layer.style?.fillOpacity ?? 0.08,
          dashArray: layer.style?.dashArray
        }),
        pointToLayer: (_, latlng) =>
          L.circleMarker(latlng, {
            radius: 4,
            color: layer.style?.stroke ?? "#30302D",
            weight: 1,
            fillColor: "#faf8f1",
            fillOpacity: 0.95
          })
      }).addTo(this.map);
    } else if (layer.type === "xyz_tile" && layer.url) {
      instance = L.tileLayer(resolveRuntimePath(layer.url), {
        opacity: layer.opacity ?? 1,
        attribution: layer.attribution ?? ""
      }).addTo(this.map);
    } else if (layer.type === "wms_tile" && layer.url) {
      instance = L.tileLayer.wms(resolveRuntimePath(layer.url), {
        opacity: layer.opacity ?? 1,
        attribution: layer.attribution ?? ""
      }).addTo(this.map);
    }

    this.activeLayers.set(layer.id, instance);
  }

  disableLayer(layerId: string): void {
    const instance = this.activeLayers.get(layerId);
    if (instance) {
      instance.remove();
    }
    this.activeLayers.delete(layerId);
    this.tiledLayers.delete(layerId);
  }

  renderObjects(index: MapObjectsIndex, language: LanguageCode, visibleIds?: Set<string>): void {
    if (this.featureLayer) {
      this.featureLayer.remove();
    }

    this.featureLayer = L.geoJSON(index.features, {
      filter: (feature) => {
        if (!visibleIds) {
          return true;
        }
        return feature.properties ? visibleIds.has(feature.properties.id) : false;
      },
      pointToLayer: (feature, latlng) => {
        const category = feature.properties?.category ?? "object";
        const isMedia = category.includes("map") || category.includes("photo") || category.includes("image");
        return L.circleMarker(latlng, {
          radius: isMedia ? 5 : 4,
          color: "#30302D",
          weight: 1.4,
          fillColor: isMedia ? "#C9821E" : "#faf8f1",
          fillOpacity: 0.95,
          dashArray: feature.properties?.geometry_certainty === "approximate" ? "4 2" : undefined
        });
      },
      onEachFeature: (feature, layer) => {
        const title = pickLanguageValue(feature.properties?.title, language).value;
        const summary = pickLanguageValue(feature.properties?.summary, language).value;
        layer.bindTooltip(`<strong>${title}</strong><br>${summary}`);
        layer.on("click", () => {
          if (feature.properties?.id && this.markerHandler) {
            this.markerHandler(feature.properties.id);
          }
        });
      }
    }).addTo(this.map);

    const bounds = this.featureLayer.getBounds();
    if (bounds.isValid()) {
      this.map.fitBounds(bounds.pad(0.16));
    }
  }

  onMarkerSelect(handler: (featureId: string) => void): void {
    this.markerHandler = handler;
  }

  invalidateSize(): void {
    this.map.invalidateSize();
  }

  private async refreshVisibleTiles(): Promise<void> {
    for (const [layerId, tileEntry] of this.tiledLayers.entries()) {
      if (!this.activeLayers.has(layerId)) {
        continue;
      }
      await updateTiledLayer(tileEntry, this.map);
    }
  }
}

async function loadGeoJsonLayer(layer: LayerDefinition): Promise<GeoJSON.FeatureCollection> {
  if (layer.tileManifestUrl) {
    const manifestResponse = await fetch(resolveRuntimePath(layer.tileManifestUrl));
    if (!manifestResponse.ok) {
      throw new Error(`Failed to load tile manifest ${layer.id}`);
    }
    const manifest = (await manifestResponse.json()) as GeoJsonTileManifest;
    const bounds = {
      south: manifest.bbox[0],
      west: manifest.bbox[1],
      north: manifest.bbox[2],
      east: manifest.bbox[3],
    };
    const tilePayloads = await Promise.all(
      manifest.tiles
        .filter((tile) => tileIntersectsBounds(tile.bbox, bounds))
        .map(async (tile) => {
          const tileResponse = await fetch(resolveRuntimePath(tile.url));
          if (!tileResponse.ok) {
            throw new Error(`Failed to load layer tile ${layer.id}: ${tile.url}`);
          }
          return (await tileResponse.json()) as GeoJSON.FeatureCollection;
        }),
    );
    return mergeCollections(tilePayloads);
  }
  if (layer.manifestUrl) {
    const manifestResponse = await fetch(resolveRuntimePath(layer.manifestUrl));
    if (!manifestResponse.ok) {
      throw new Error(`Failed to load layer manifest ${layer.id}`);
    }
    const manifest = (await manifestResponse.json()) as GeoJsonBundleManifest;
    const chunkPayloads = await Promise.all(
      manifest.chunks.map(async (chunk) => {
        const chunkResponse = await fetch(resolveRuntimePath(chunk.url));
        if (!chunkResponse.ok) {
          throw new Error(`Failed to load layer chunk ${layer.id}: ${chunk.url}`);
        }
        return (await chunkResponse.json()) as GeoJSON.FeatureCollection;
      }),
    );
    return {
      type: "FeatureCollection",
      features: chunkPayloads.flatMap((payload) => payload.features ?? []),
    };
  }

  const response = await fetch(resolveRuntimePath(layer.url!));
  if (!response.ok) {
    throw new Error(`Failed to load layer ${layer.id}`);
  }
  return (await response.json()) as GeoJSON.FeatureCollection;
}

async function createTiledLayer(layer: LayerDefinition, map: L.Map): Promise<TileCacheEntry> {
  const manifestResponse = await fetch(resolveRuntimePath(layer.tileManifestUrl!));
  if (!manifestResponse.ok) {
    throw new Error(`Failed to load tile manifest ${layer.id}`);
  }
  const manifest = (await manifestResponse.json()) as GeoJsonTileManifest;
  const layerInstance = L.geoJSON(undefined, {
    style: () => ({
      color: layer.style?.stroke ?? "#30302D",
      weight: layer.style?.strokeWidth ?? 1,
      opacity: layer.style?.strokeOpacity ?? 1,
      fillColor: layer.style?.fill ?? layer.style?.stroke ?? "#30302D",
      fillOpacity: layer.style?.fillOpacity ?? 0.08,
      dashArray: layer.style?.dashArray,
    }),
    pointToLayer: (_, latlng) =>
      L.circleMarker(latlng, {
        radius: 4,
        color: layer.style?.stroke ?? "#30302D",
        weight: 1,
        fillColor: "#faf8f1",
        fillOpacity: 0.95,
      }),
  }).addTo(map);
  const entry = {
    manifest,
    tiles: new Map<string, GeoJSON.FeatureCollection>(),
    layer: layerInstance,
  };
  await updateTiledLayer(entry, map);
  return entry;
}

async function updateTiledLayer(entry: TileCacheEntry, map: L.Map): Promise<void> {
  const bounds = map.getBounds();
  const viewport = {
    south: bounds.getSouth(),
    west: bounds.getWest(),
    north: bounds.getNorth(),
    east: bounds.getEast(),
  };
  const neededTiles = entry.manifest.tiles.filter((tile) => tileIntersectsBounds(tile.bbox, viewport));
  await Promise.all(
    neededTiles.map(async (tile) => {
      if (entry.tiles.has(tile.url)) {
        return;
      }
      const response = await fetch(resolveRuntimePath(tile.url));
      if (!response.ok) {
        throw new Error(`Failed to load tile ${tile.url}`);
      }
      entry.tiles.set(tile.url, (await response.json()) as GeoJSON.FeatureCollection);
    }),
  );
  const collection = mergeCollections(neededTiles.map((tile) => entry.tiles.get(tile.url)).filter(Boolean) as GeoJSON.FeatureCollection[]);
  entry.layer.clearLayers();
  entry.layer.addData(collection);
}

function mergeCollections(collections: GeoJSON.FeatureCollection[]): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  const seen = new Set<string>();
  collections.forEach((collection) => {
    collection.features.forEach((feature) => {
      const key = featureKey(feature);
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      features.push(feature);
    });
  });
  return { type: "FeatureCollection", features };
}

function tileIntersectsBounds(
  tileBbox: [number, number, number, number],
  bounds: { south: number; west: number; north: number; east: number },
): boolean {
  return !(tileBbox[3] < bounds.west || tileBbox[1] > bounds.east || tileBbox[2] < bounds.south || tileBbox[0] > bounds.north);
}

function featureKey(feature: GeoJSON.Feature): string {
  const props = (feature.properties ?? {}) as Record<string, unknown>;
  if (props.osm_type && props.osm_id) {
    return `${String(props.osm_type)}:${String(props.osm_id)}`;
  }
  return JSON.stringify(feature.geometry ?? {}) + JSON.stringify(props.name ?? "");
}
