import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

type OnboardBody = { name?: string; email?: string | null; phone?: string | null; preferredChannel?: "email" | "whatsapp" };

export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const { data: authData, error: authError } = await supabase.auth.getUser();
  if (authError || !authData.user) return NextResponse.json({ error: "Sessão inválida." }, { status: 401 });

  const body = (await request.json()) as OnboardBody;
  const name = body.name?.trim();
  const channel = body.preferredChannel === "whatsapp" ? "whatsapp" : "email";
  const verifiedEmail = authData.user.email?.trim().toLowerCase() ?? null;
  const verifiedPhone = authData.user.phone?.trim() ?? null;
  const phone = verifiedPhone ?? body.phone?.trim() ?? null;
  if (!name || name.length < 2 || (!verifiedEmail && !phone)) return NextResponse.json({ error: "Dados de acesso incompletos." }, { status: 400 });

  const admin = createAdminClient();
  const { data: contactByUser, error: existingError } = await admin.from("contacts").select("id,trial_started_at").eq("auth_user_id", authData.user.id).maybeSingle();
  if (existingError) {
    console.error("contact_lookup_error", existingError);
    return NextResponse.json({ error: "Não foi possível preparar o acesso." }, { status: 500 });
  }

  let existing = contactByUser;
  if (!existing && verifiedEmail) {
    const emailPattern = verifiedEmail.replace(/[\\%_]/g, "\\$&");
    const { data: contactByEmail, error: emailLookupError } = await admin.from("contacts").select("id,trial_started_at").ilike("email", emailPattern).is("auth_user_id", null).maybeSingle();
    if (emailLookupError) {
      console.error("contact_email_lookup_error", emailLookupError);
      return NextResponse.json({ error: "Não foi possível preparar o acesso." }, { status: 500 });
    }
    existing = contactByEmail;
  }

  const now = new Date();
  let contact = existing;
  const shouldCreateTrial = !existing?.trial_started_at;

  if (!contact) {
    const { data: created, error } = await admin.from("contacts").insert({
      name,
      email: verifiedEmail,
      phone,
      auth_user_id: authData.user.id,
      preferred_channel: channel,
      verified_at: now.toISOString(),
      lifecycle: "trial",
    }).select("id,trial_started_at").single();
    if (error || !created) {
      console.error("contact_create_error", error);
      return NextResponse.json({ error: "Não foi possível criar o acesso." }, { status: 500 });
    }
    contact = created;
  } else {
    const { error: updateError } = await admin.from("contacts").update({
      name,
      email: verifiedEmail,
      phone,
      auth_user_id: authData.user.id,
      preferred_channel: channel,
      verified_at: now.toISOString(),
    }).eq("id", contact.id);
    if (updateError) {
      console.error("contact_update_error", updateError);
      return NextResponse.json({ error: "Não foi possível atualizar o acesso." }, { status: 500 });
    }
  }

  const { data: trial } = await admin.from("subscriptions").select("id,starts_at,ends_at").eq("contact_id", contact.id).eq("plan", "Teste gratuito").maybeSingle();
  if (trial && !contact.trial_started_at) {
    await admin.from("contacts").update({ trial_started_at: trial.starts_at }).eq("id", contact.id);
  }

  if (!trial && shouldCreateTrial) {
    const endsAt = new Date(now.getTime() + 48 * 60 * 60 * 1000);
    const { error } = await admin.from("subscriptions").insert({
      contact_id: contact.id,
      plan: "Teste gratuito",
      amount: 0,
      starts_at: now.toISOString(),
      ends_at: endsAt.toISOString(),
    });
    if (error) {
      console.error("trial_create_error", error);
      return NextResponse.json({ error: "Não foi possível ativar o teste gratuito." }, { status: 500 });
    }
    await admin.from("contacts").update({ lifecycle: "trial", trial_started_at: now.toISOString() }).eq("id", contact.id);
    await admin.from("agent_activity").insert({ agent: "Agente de Acesso", action: "Teste gratuito ativado", detail: `${name}: acesso de 48 horas iniciado.` });
  }

  return NextResponse.json({ ok: true });
}
