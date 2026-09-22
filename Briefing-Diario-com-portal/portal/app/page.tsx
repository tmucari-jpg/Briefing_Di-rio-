import { redirect } from "next/navigation";
import { AccessFlow } from "@/components/access-flow";
import { createClient } from "@/lib/supabase/server";

export default async function HomePage() {
  const supabase = await createClient();
  const { data } = await supabase.auth.getUser();
  if (data.user) redirect("/leitor");

  return (
    <main className="auth-page">
      <section className="auth-copy">
        <div className="brand-mark">BD</div>
        <p className="eyebrow">BRIEFING DIÁRIO</p>
        <h1>Mais informação.<br />Melhores decisões.</h1>
        <p className="lead">Notícias, contexto e oportunidades de Moçambique, África e do mundo, organizadas para si.</p>
        <div className="benefits">
          <span>10 notícias essenciais por edição</span>
          <span>Radar de oportunidades</span>
          <span>2 dias de teste gratuito</span>
        </div>
      </section>
      <section className="auth-card" aria-label="Acesso ao Briefing Diário"><AccessFlow /></section>
    </main>
  );
}
