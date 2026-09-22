function required(name: string) {
  const value = process.env[name];
  if (!value) throw new Error(`Variável obrigatória em falta: ${name}`);
  return value;
}

export const publicEnv = () => ({
  supabaseUrl: required("NEXT_PUBLIC_SUPABASE_URL"),
  supabasePublishableKey: required("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"),
});

export const privateEnv = () => ({
  ...publicEnv(),
  serviceRoleKey: required("SUPABASE_SERVICE_ROLE_KEY"),
  adminEmail: required("ADMIN_EMAIL").trim().toLowerCase(),
});
