import { CalendarDays, ExternalLink, LogOut, Radar } from "lucide-react";
import { redirect } from "next/navigation";
import { PaymentForm } from "@/components/payment-form";
import { createClient } from "@/lib/supabase/server";

type NewsItem = { section?: string; title?: string; summary?: string; why?: string; impact?: string; source?: string; link?: string; published?: string };
type OpportunityItem = NewsItem & { category?: string; action?: string };
type BriefingPayload = { updated_at?: string; items?: NewsItem[]; opportunities?: OpportunityItem[] };

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-MZ", { dateStyle: "long", timeStyle: "short", timeZone: "Africa/Maputo" }).format(new Date(value));
}

export default async function ReaderPage() {
  const supabase = await createClient();
  const { data: authData } = await supabase.auth.getUser();
  if (!authData.user) redirect("/");

  const now = new Date().toISOString();
  const [{ data: contact }, { data: subscription }, { data: briefings }] = await Promise.all([
    supabase.from("contacts").select("id,name,preferred_channel").eq("auth_user_id", authData.user.id).maybeSingle(),
    supabase.from("subscriptions").select("plan,starts_at,ends_at").lte("starts_at", now).gt("ends_at", now).order("ends_at", { ascending: false }).limit(1).maybeSingle(),
    supabase.from("briefings").select("language,payload,published_at").eq("language", "pt").order("published_at", { ascending: false }).limit(1),
  ]);

  const briefing = briefings?.[0] as { language: string; payload: BriefingPayload; published_at: string } | undefined;
  const items = briefing?.payload?.items ?? [];
  const opportunities = briefing?.payload?.opportunities ?? [];

  return (
    <main className="reader-page">
      <header className="reader-header">
        <a className="reader-brand" href="/leitor"><span className="brand-mark small">BD</span><span><strong>Briefing</strong><br />Diário</span></a>
        <div className="reader-actions">
          <span className={`access-pill ${subscription ? "active" : "expired"}`}>{subscription ? `${subscription.plan} ativo` : "Acesso pendente"}</span>
          <form action="/api/logout" method="post"><button className="icon-button" title="Terminar sessão" type="submit"><LogOut size={18} /></button></form>
        </div>
      </header>

      <section className="reader-hero">
        <div><p className="eyebrow">BOM DIA, {contact?.name?.toUpperCase() ?? "ASSINANTE"}</p><h1>O que merece a sua atenção hoje.</h1><p className="lead">Informação selecionada, contextualizada e organizada para decisões mais rápidas.</p></div>
        {subscription && <div className="subscription-card"><CalendarDays size={22} /><div><small>Acesso disponível até</small><strong>{formatDate(subscription.ends_at)}</strong></div></div>}
      </section>

      {!subscription ? (
        <><section className="empty-state"><Radar size={34} /><h2>Escolha um plano para continuar</h2><p>O seu teste terminou ou ainda não existe uma subscrição ativa.</p></section><PaymentForm /></>
      ) : items.length === 0 ? (
        <section className="empty-state"><Radar size={34} /><h2>Primeira edição em preparação</h2><p>O seu acesso está ativo. Os agentes estão a preparar o briefing protegido.</p></section>
      ) : (
        <>
          <div className="section-heading"><div><p className="eyebrow">EDIÇÃO MAIS RECENTE</p><h2>Destaques do dia</h2></div><span>{formatDate(briefing?.published_at ?? new Date().toISOString())}</span></div>
          <section className="news-grid">
            {items.map((item, index) => <article className="news-card" key={`${item.link ?? item.title}-${index}`}>
              <div className="news-meta"><span>{item.section ?? "Destaque"}</span><small>{item.source ?? "Fonte verificada"}</small></div><h3>{item.title}</h3><p>{item.summary}</p>
              {item.why && <div className="context-box"><strong>Porque importa</strong><span>{item.why}</span></div>}
              {item.link && <a href={item.link} target="_blank" rel="noreferrer">Consultar fonte <ExternalLink size={15} /></a>}
            </article>)}
          </section>

          {opportunities.length > 0 && <>
            <div className="section-heading opportunity-heading"><div><p className="eyebrow">RADAR DE OPORTUNIDADES</p><h2>Possibilidades para acompanhar</h2></div><span>{opportunities.length} oportunidades identificadas</span></div>
            <section className="news-grid">
              {opportunities.map((item, index) => <article className="news-card opportunity-card" key={`${item.link ?? item.title}-${index}`}>
                <div className="news-meta"><span>{item.category ?? item.section ?? "Oportunidade"}</span><small>{item.source ?? "Fonte verificada"}</small></div><h3>{item.title}</h3><p>{item.summary}</p>
                {item.action && <div className="context-box opportunity-action"><strong>Próxima ação</strong><span>{item.action}</span></div>}
                {item.link && <a href={item.link} target="_blank" rel="noreferrer">Consultar oportunidade <ExternalLink size={15} /></a>}
              </article>)}
            </section>
          </>}
          <PaymentForm />
        </>
      )}
    </main>
  );
}
