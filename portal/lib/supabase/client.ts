import { createBrowserClient } from "@supabase/ssr";
import { publicEnv } from "@/lib/env";

export function createClient() {
  const env = publicEnv();
  return createBrowserClient(env.supabaseUrl, env.supabasePublishableKey);
}
