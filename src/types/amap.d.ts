declare namespace AMap {
  class Map {
    constructor(container: HTMLElement, opts?: MapOptions);
    destroy(): void;
    addControl(control: unknown): void;
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

  class MarkerCluster {
    constructor(map: Map, markers: Marker[], opts?: MarkerClusterOptions);
    setMap(map: Map | null): void;
    setMarkers(markers: Marker[]): void;
  }

  interface MarkerClusterOptions {
    gridSize?: number;
    maxZoom?: number;
    minClusterSize?: number;
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
