import { createClient } from "@/lib/supabase/server";
import { privateEnv } from "@/lib/env";

export async function getAdmin() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user?.email) return null;
  return data.user.email.toLowerCase() === privateEnv().adminEmail ? data.user : null;
}
