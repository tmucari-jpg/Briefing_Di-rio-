import { createClient } from "@supabase/supabase-js";
import { privateEnv } from "@/lib/env";

export function createAdminClient() {
  const env = privateEnv();
  return createClient(env.supabaseUrl, env.serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
