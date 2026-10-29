import { forwardControl } from "@/lib/control";

export async function POST() {
  return forwardControl("/api/control/resume");
}

export const dynamic = "force-dynamic";
