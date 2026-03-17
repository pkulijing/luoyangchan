"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export default function BackButton() {
  const router = useRouter();
  return (
    <Button variant="ghost" onClick={() => router.push("/")}>
      ← 返回地图
    </Button>
  );
}
