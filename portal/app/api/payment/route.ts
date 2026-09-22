import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";
import { isPaidPlan, PLAN_PRICES } from "@/lib/plans";

export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const { data: authData, error: authError } = await supabase.auth.getUser();
  if (authError || !authData.user) return NextResponse.json({ error: "Sessão inválida." }, { status: 401 });

  const body = (await request.json()) as { plan?: string; transactionRef?: string; payerPhone?: string };
  if (!isPaidPlan(body.plan) || !body.transactionRef?.trim() || !body.payerPhone?.trim()) {
    return NextResponse.json({ error: "Preencha o plano, número e referência." }, { status: 400 });
  }

  const admin = createAdminClient();
  const { data: contact, error: contactError } = await admin.from("contacts").select("id,name").eq("auth_user_id", authData.user.id).single();
  if (contactError || !contact) return NextResponse.json({ error: "Contacto não encontrado." }, { status: 404 });

  const { data: payment, error } = await admin.from("payments").insert({
    contact_id: contact.id,
    plan: body.plan,
    amount: PLAN_PRICES[body.plan],
    transaction_ref: body.transactionRef.trim(),
    payer_phone: body.payerPhone.trim(),
    payment_method: "emola_payizi",
    provider: "manual",
  }).select("id,status").single();

  if (error) {
    if (error.code === "23505") return NextResponse.json({ error: "Esta referência já foi registada." }, { status: 409 });
    console.error("payment_create_error", error);
    return NextResponse.json({ error: "Não foi possível registar o pagamento." }, { status: 500 });
  }

  await admin.from("agent_activity").insert({
    agent: "Agente de Pagamentos",
    action: "Pagamento recebido",
    detail: `${contact.name}: plano ${body.plan} aguarda confirmação.`,
  });
  return NextResponse.json({ payment }, { status: 201 });
}
