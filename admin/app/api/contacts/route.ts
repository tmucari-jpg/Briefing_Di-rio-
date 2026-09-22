import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { requireApiAdmin, serverError, unauthorized } from "../_shared";

export async function POST(request: NextRequest) {
  if (!(await requireApiAdmin())) return unauthorized();
  try {
    const body = (await request.json()) as Record<string, string>;
    const name = body.name?.trim();
    const email = body.email?.trim().toLowerCase();
    const phone = body.phone?.trim();
    if (!name || !email || !phone) return NextResponse.json({ error: "Nome, email e telefone são obrigatórios." }, { status: 400 });

    const supabase = createAdminClient();
    const { data: contact, error } = await supabase.from("contacts").insert({
      name,
      email,
      phone,
      country: body.country?.trim() || "Moçambique",
      interest: body.interest?.trim() || "Informação empresarial",
    }).select().single();
    if (error) throw error;

    await supabase.from("agent_activity").insert({ agent: "Agente de Leads", action: "Contacto registado", detail: `${name} entrou na carteira comercial.` });
    return NextResponse.json({ contact }, { status: 201 });
  } catch (error) {
    return serverError("contact_create_error", error);
  }
}
