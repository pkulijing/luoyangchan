declare namespace AMap {
  class Map {
    constructor(container: HTMLElement, opts?: MapOptions);
    destroy(): void;
    addControl(control: unknown): void;
    setFitView(
      overlays?: unknown[] | null,
      immediately?: boolean,
      avoid?: [number, number, number, number] | number[]
    ): void;
    getZoom(): number;
    getCenter(): LngLat;
    setZoom(zoom: number): void;
    setCenter(center: [number, number] | LngLat): void;
  }

  interface MapOptions {
    zoom?: number;
    center?: [number, number] | LngLat;
    viewMode?: "2D" | "3D";
    mapStyle?: string;
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
    on(event: string, handler: (...args: unknown[]) => void): void;
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

  // AMap JS API 2.0: MarkerCluster 是数据驱动模式，第二个参数为数据点数组
  class MarkerCluster {
    constructor(map: Map, dataOptions: MarkerClusterDataOption[], opts?: MarkerClusterOptions);
    setMap(map: Map | null): void;
  }

  interface MarkerClusterDataOption {
    lnglat: [number, number] | LngLat;
    [key: string]: unknown;
  }

  interface MarkerClusterRenderContext {
    marker: Marker;
    count: number;
    data: MarkerClusterDataOption[];
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
  }

  interface InfoWindowOptions {
    content?: string | HTMLElement;
    offset?: Pixel;
    isCustom?: boolean;
  }

  class Scale {
    constructor(opts?: object);
  }

  class ToolBar {
    constructor(opts?: { position?: string });
  }

  class Geocoder {
    constructor(opts?: object);
    getAddress(
      lnglat: LngLat | [number, number],
      callback: (status: string, result: unknown) => void
    ): void;
  }
}

interface Window {
  AMap: typeof AMap;
}
