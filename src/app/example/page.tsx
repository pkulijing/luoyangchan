import Link from "next/link";

const examples = [
  { name: "AMap", path: "/example/amap", desc: "高德 JS API 2.0 底图 + MarkerCluster" },
  { name: "Tianditu", path: "/example/tianditu", desc: "天地图 WMTS 底图加载" },
  { name: "Marker", path: "/example/marker", desc: "Leaflet Marker 基础用法" },
  { name: "MarkerCluster", path: "/example/markercluster", desc: "MarkerCluster 聚合展示" },
];

export default function ExampleIndex() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-2xl font-bold mb-6">Example Pages</h1>
      <div className="grid gap-4 max-w-md">
        {examples.map((ex) => (
          <Link
            key={ex.path}
            href={ex.path}
            className="block rounded-lg border bg-white p-4 hover:border-blue-500 hover:shadow-sm transition-colors"
          >
            <div className="font-medium">{ex.name}</div>
            <div className="text-sm text-gray-500">{ex.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
