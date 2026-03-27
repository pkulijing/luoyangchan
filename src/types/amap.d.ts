declare namespace AMap {
  class Map {
    constructor(container: HTMLElement | string, opts?: MapOptions);
    destroy(): void;
    addControl(control: unknown): void;
    setFitView(
      overlays?: unknown[] | null,
      immediately?: boolean,
      avoid?: number[],
      maxZoom?: number,
    ): void;
    getZoom(): number;
    getCenter(): LngLat;
    setZoom(zoom: number): void;
    setCenter(center: [number, number] | LngLat): void;
    setZoomAndCenter(
      zoom: number,
      center: [number, number] | LngLat,
      immediately?: boolean,
    ): void;
    on(event: string, handler: (...args: unknown[]) => void): void;
    off(event: string, handler: (...args: unknown[]) => void): void;
    closeInfoWindow(): void;
    getContainer(): HTMLElement;
  }

  interface MapOptions {
    zoom?: number;
    center?: [number, number] | LngLat;
    viewMode?: "2D" | "3D";
    mapStyle?: string;
    zooms?: [number, number];
    dragEnable?: boolean;
    zoomEnable?: boolean;
    scrollWheel?: boolean;
  }

  class LngLat {
    constructor(lng: number, lat: number);
    getLng(): number;
    getLat(): number;
  }

  class Pixel {
    constructor(x: number, y: number);
  }

  class Marker {
    constructor(opts?: MarkerOptions);
    setMap(map: Map | null): void;
    setContent(content: string | HTMLElement): void;
    setOffset(offset: Pixel): void;
    setTitle(title: string): void;
    setPosition(position: [number, number] | LngLat): void;
    on(event: string, handler: (...args: unknown[]) => void): void;
    off(event: string, handler: (...args: unknown[]) => void): void;
    getExtData(): unknown;
  }

  interface MarkerOptions {
    position?: LngLat | [number, number];
    title?: string;
    content?: string | HTMLElement;
    offset?: Pixel;
    map?: Map;
    extData?: unknown;
  }

  class MarkerCluster {
    constructor(
      map: Map,
      dataOptions: MarkerClusterDataOption[],
      opts?: MarkerClusterOptions,
    );
    setMap(map: Map | null): void;
    setData(data: MarkerClusterDataOption[]): void;
  }

  interface MarkerClusterDataOption {
    lnglat: [number, number] | LngLat;
    [key: string]: unknown;
  }

  interface MarkerClusterRenderContext {
    marker: Marker;
    count: number;
    data: MarkerClusterDataOption[];
    clusterData: MarkerClusterDataOption[];
  }

  interface MarkerClusterOptions {
    gridSize?: number;
    maxZoom?: number;
    minClusterSize?: number;
    renderMarker?: (context: MarkerClusterRenderContext) => void;
    renderClusterMarker?: (context: MarkerClusterRenderContext) => void;
  }

  class InfoWindow {
    constructor(opts?: InfoWindowOptions);
    open(map: Map, position: LngLat | [number, number]): void;
    close(): void;
    setContent(content: string | HTMLElement): void;
    on(event: string, handler: (...args: unknown[]) => void): void;
    getIsOpen(): boolean;
  }

  interface InfoWindowOptions {
    content?: string | HTMLElement;
    offset?: Pixel;
    isCustom?: boolean;
    anchor?: string;
  }

  class Scale {
    constructor(opts?: object);
  }

  class ToolBar {
    constructor(opts?: { position?: string });
  }

  class Geolocation {
    constructor(opts?: GeolocationOptions);
    getCurrentPosition(
      callback: (status: string, result: GeolocationResult) => void,
    ): void;
  }

  interface GeolocationOptions {
    enableHighAccuracy?: boolean;
    timeout?: number;
    maximumAge?: number;
    showButton?: boolean;
    showMarker?: boolean;
    showCircle?: boolean;
  }

  interface GeolocationResult {
    position: LngLat;
    accuracy: number;
    message: string;
  }
}

interface Window {
  AMap: typeof AMap;
}
