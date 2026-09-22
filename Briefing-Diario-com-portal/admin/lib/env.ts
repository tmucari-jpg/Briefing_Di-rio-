function required(value: string | undefined, name: string) {
  if (!value) throw new Error(`Variável obrigatória em falta: ${name}`);
  return value;
}

export const publicEnv = () => ({
  supabaseUrl: required(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    "NEXT_PUBLIC_SUPABASE_URL",
  ),
  supabasePublishableKey: required(
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  ),
});

export const privateEnv = () => ({
  ...publicEnv(),
  serviceRoleKey: required(
    process.env.SUPABASE_SERVICE_ROLE_KEY,
    "SUPABASE_SERVICE_ROLE_KEY",
  ),
  adminEmail: required(process.env.ADMIN_EMAIL, "ADMIN_EMAIL")
    .trim()
    .toLowerCase(),
});
