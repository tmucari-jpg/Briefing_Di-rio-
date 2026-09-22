import { NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import type { AgentActivity, Contact, Payment, Subscription } from "@/lib/types";
import { requireApiAdmin, serverError, unauthorized } from "../_shared";

export const dynamic = "force-dynamic";

export async function GET() {
  if (!(await requireApiAdmin())) return unauthorized();
  try {
    const supabase = createAdminClient();
    const now = new Date().toISOString();
    const [contactsResult, paymentsResult, subscriptionsResult, activityResult, revenueResult] = await Promise.all([
      supabase.from("contacts").select("*").order("created_at", { ascending: false }).limit(50),
      supabase.from("payments").select("*, contacts(*)").eq("status", "pending").order("created_at", { ascending: false }).limit(50),
      supabase.from("subscriptions").select("*, contacts(*)").gt("ends_at", now).order("ends_at", { ascending: true }).limit(50),
      supabase.from("agent_activity").select("*").order("created_at", { ascending: false }).limit(20),
      supabase.from("payments").select("amount").eq("status", "confirmed"),
    ]);

    const firstError = [contactsResult, paymentsResult, subscriptionsResult, activityResult, revenueResult].find((result) => result.error)?.error;
    if (firstError) throw firstError;

    const contacts = (contactsResult.data ?? []) as Contact[];
    const pendingPayments = (paymentsResult.data ?? []) as unknown as Payment[];
    const activeSubscriptions = (subscriptionsResult.data ?? []) as unknown as Subscription[];
    const activity = (activityResult.data ?? []) as AgentActivity[];
    const revenue = (revenueResult.data ?? []).reduce((total, item) => total + Number(item.amount ?? 0), 0);

    return NextResponse.json({
      contacts,
      pendingPayments,
      activeSubscriptions,
      activity,
      metrics: { contacts: contacts.length, pending: pendingPayments.length, active: activeSubscriptions.length, revenue },
      merchant: { status: "pending", label: "Dados Pay IZI por inserir" },
    });
  } catch (error) {
    return serverError("overview_error", error);
  }
}
