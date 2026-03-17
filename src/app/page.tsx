import MapView from "@/components/MapView";
import { getAllSites } from "@/lib/supabase/queries";

export default async function Home() {
  const sites = await getAllSites();
  return <MapView sites={sites} />;
}
