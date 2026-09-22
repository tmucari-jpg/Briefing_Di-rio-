import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { addPlanDuration, isPaidPlan } from "@/lib/plans";
import { requireApiAdmin, serverError, unauthorized } from "../../../_shared";

export async function POST(_request: NextRequest, context: { params: Promise<{ id: string }> }) {
  if (!(await requireApiAdmin())) return unauthorized();
  try {
    const { id } = await context.params;
    const supabase = createAdminClient();
    const { data: payment, error: paymentError } = await supabase.from("payments").select("*, contacts(name)").eq("id", id).single();
    if (paymentError || !payment || !isPaidPlan(payment.plan)) return NextResponse.json({ error: "Pagamento não encontrado." }, { status: 404 });

    const { data: existing } = await supabase.from("subscriptions").select("*").eq("payment_id", id).maybeSingle();
    let subscription = existing;
    if (!subscription) {
      const now = new Date();
      const { data: current } = await supabase.from("subscriptions").select("ends_at").eq("contact_id", payment.contact_id).gt("ends_at", now.toISOString()).order("ends_at", { ascending: false }).limit(1).maybeSingle();
      const startsAt = current?.ends_at ? new Date(current.ends_at) : now;
      const endsAt = addPlanDuration(startsAt, payment.plan);
      const { data: created, error } = await supabase.from("subscriptions").insert({ contact_id: payment.contact_id, payment_id: id, plan: payment.plan, amount: payment.amount, starts_at: startsAt.toISOString(), ends_at: endsAt.toISOString() }).select().single();
      if (error) throw error;
      subscription = created;
    }

    const confirmedAt = new Date().toISOString();
    const { error: confirmError } = await supabase.from("payments").update({ status: "confirmed", confirmed_at: confirmedAt }).eq("id", id);
    if (confirmError) throw confirmError;
    await supabase.from("contacts").update({ lifecycle: "active" }).eq("id", payment.contact_id);
    if (payment.status !== "confirmed") {
      const contactName = Array.isArray(payment.contacts) ? payment.contacts[0]?.name : payment.contacts?.name;
      await supabase.from("agent_activity").insert({ agent: "Agente de Acesso", action: "Subscrição ativada", detail: `${contactName ?? "Cliente"}: plano ${payment.plan} confirmado.` });
    }
    return NextResponse.json({ subscription });
  } catch (error) {
    return serverError("payment_confirm_error", error);
  }
}
