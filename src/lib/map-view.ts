import L from "leaflet";
import type {
  GeoFeatureProperties,
  GeoJsonBundleManifest,
  LanguageCode,
  LayerDefinition,
  LayersConfig,
  MapObjectsIndex,
} from "./types";
import { pickLanguageValue } from "./i18n";
import { resolveRuntimePath } from "./runtime-path";

type LayerInstance = L.Layer | null;

export class AtlasMap {
  private map: L.Map;
  private activeLayers = new Map<string, LayerInstance>();
  private featureLayer: L.GeoJSON<GeoJSON.Geometry, GeoFeatureProperties> | null = null;
  private markerHandler: ((featureId: string) => void) | null = null;

  constructor(container: HTMLElement) {
    this.map = L.map(container, {
      zoomControl: false,
      attributionControl: true
    }).setView([52.08, 6.54], 11);
    L.control.zoom({ position: "bottomright" }).addTo(this.map);
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
    if (layer.type === "geojson" && (layer.url || layer.manifestUrl)) {
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
}

async function loadGeoJsonLayer(layer: LayerDefinition): Promise<GeoJSON.FeatureCollection> {
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
