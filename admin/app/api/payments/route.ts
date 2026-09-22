import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { isPaidPlan, PLAN_PRICES } from "@/lib/plans";
import { requireApiAdmin, serverError, unauthorized } from "../_shared";

export async function POST(request: NextRequest) {
  if (!(await requireApiAdmin())) return unauthorized();
  try {
    const body = (await request.json()) as { contactId?: string; plan?: string; transactionRef?: string; payerPhone?: string };
    if (!body.contactId || !isPaidPlan(body.plan) || !body.transactionRef?.trim() || !body.payerPhone?.trim()) {
      return NextResponse.json({ error: "Preencha todos os dados do pagamento." }, { status: 400 });
    }
    const supabase = createAdminClient();
    const { data: payment, error } = await supabase.from("payments").insert({
      contact_id: body.contactId,
      plan: body.plan,
      amount: PLAN_PRICES[body.plan],
      transaction_ref: body.transactionRef.trim(),
      payer_phone: body.payerPhone.trim(),
    }).select().single();
    if (error) throw error;
    await supabase.from("agent_activity").insert({ agent: "Agente de Pagamentos", action: "Pagamento recebido", detail: `Transação ${body.transactionRef.trim()} aguarda confirmação.` });
    return NextResponse.json({ payment }, { status: 201 });
  } catch (error) {
    return serverError("payment_create_error", error);
  }
}
