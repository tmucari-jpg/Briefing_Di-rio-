import { redirect } from "next/navigation";
import { getAdmin } from "@/lib/auth";
import Dashboard from "@/components/dashboard";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const admin = await getAdmin();
  if (!admin) redirect("/login");
  return <Dashboard adminEmail={admin.email ?? ""} />;
}
