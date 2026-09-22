import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireApiAdmin, serverError, unauthorized } from "../_shared";

export async function POST(request: NextRequest) {
  if (!(await requireApiAdmin())) return unauthorized();
  try {
    const { contactId } = (await request.json()) as { contactId?: string };
    if (!contactId) return NextResponse.json({ error: "Contacto inválido." }, { status: 400 });
    const supabase = createAdminClient();
    const { data: contact, error: contactError } = await supabase.from("contacts").select("id,name").eq("id", contactId).single();
    if (contactError || !contact) return NextResponse.json({ error: "Contacto não encontrado." }, { status: 404 });
    const { data: previous } = await supabase.from("subscriptions").select("id").eq("contact_id", contactId).eq("plan", "Teste gratuito").limit(1);
    if (previous?.length) return NextResponse.json({ error: "Este contacto já utilizou o teste gratuito." }, { status: 409 });

    const startsAt = new Date();
    const endsAt = new Date(startsAt.getTime() + 48 * 60 * 60 * 1000);
    const { data: trial, error } = await supabase.from("subscriptions").insert({ contact_id: contactId, plan: "Teste gratuito", amount: 0, starts_at: startsAt.toISOString(), ends_at: endsAt.toISOString() }).select().single();
    if (error) throw error;
    await supabase.from("contacts").update({ lifecycle: "trial" }).eq("id", contactId);
    await supabase.from("agent_activity").insert({ agent: "Agente de Testes", action: "Teste ativado", detail: `Teste de 48 horas ativado para ${contact.name}.` });
    return NextResponse.json({ trial });
  } catch (error) {
    return serverError("trial_create_error", error);
  }
}
