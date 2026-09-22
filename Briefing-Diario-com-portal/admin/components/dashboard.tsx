"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";
import { Activity, BadgeCheck, Clock3, CreditCard, LogOut, Plus, RefreshCw, Sparkles, Users, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { PLAN_PRICES } from "@/lib/plans";
import type { Contact, Overview } from "@/lib/types";

async function api(path: string, init?: RequestInit) {
  const response = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Ocorreu um erro.");
  return data;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-PT", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
}

export default function Dashboard({ adminEmail }: { adminEmail: string }) {
  const router = useRouter();
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<"contact" | "payment" | null>(null);

  const load = useCallback(async () => {
    setError("");
    try { setData(await api("/api/overview", { cache: "no-store" })); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível carregar o painel."); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function submitContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const payload = Object.fromEntries(new FormData(event.currentTarget));
      await api("/api/contacts", { method: "POST", body: JSON.stringify(payload) });
      setModal(null); setNotice("Contacto registado com sucesso."); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao registar contacto."); }
    finally { setBusy(false); }
  }

  async function submitPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const payload = Object.fromEntries(new FormData(event.currentTarget));
      await api("/api/payments", { method: "POST", body: JSON.stringify(payload) });
      setModal(null); setNotice("Pagamento registado para validação."); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao registar pagamento."); }
    finally { setBusy(false); }
  }

  async function activateTrial(contactId: string) {
    setBusy(true); setError(""); setNotice("");
    try { await api("/api/trials", { method: "POST", body: JSON.stringify({ contactId }) }); setNotice("Teste gratuito ativado por 48 horas."); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Erro ao ativar teste."); }
    finally { setBusy(false); }
  }

  async function confirmPayment(id: string) {
    setBusy(true); setError(""); setNotice("");
    try { await api(`/api/payments/${id}/confirm`, { method: "POST" }); setNotice("Pagamento confirmado e subscrição ativada."); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Erro ao confirmar pagamento."); }
    finally { setBusy(false); }
  }

  async function signOut() {
    await api("/api/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  return (
    <main className="app-shell">
      <aside className="sidebar-panel">
        <div className="logo-lockup"><span className="logo-symbol">BD</span><span>Briefing<br/>Diário</span></div>
        <nav aria-label="Navegação principal">
          <a className="nav-item active" href="#resumo"><Activity/>Resumo</a>
          <a className="nav-item" href="#contactos"><Users/>Contactos</a>
          <a className="nav-item" href="#pagamentos"><CreditCard/>Pagamentos</a>
          <a className="nav-item" href="#subscricoes"><BadgeCheck/>Subscrições</a>
        </nav>
        <div className="agent-note"><Sparkles/><div><strong>Força agêntica</strong><span>Operação preparada</span></div></div>
        <button className="signout" onClick={() => void signOut()}><LogOut/>Terminar sessão</button>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div><p className="eyebrow">Centro de operações</p><h1>Briefing Diário</h1><p>Testes, pagamentos e acessos num único lugar.</p></div>
          <div className="top-actions">
            <button className="secondary-button" onClick={() => void load()}><RefreshCw/>Atualizar</button>
            <button className="primary-button compact" onClick={() => setModal("contact")}><Plus/>Novo contacto</button>
          </div>
        </header>

        <div className="admin-chip">Sessão: {adminEmail}</div>
        {(error || notice) && <div className={error ? "notice error" : "notice success"} role="status">{error || notice}</div>}

        <section id="resumo" className="metric-grid" aria-label="Resumo operacional">
          <Metric icon={<Users/>} label="Contactos" value={data?.metrics.contacts ?? "—"} detail="carteira registada"/>
          <Metric icon={<Clock3/>} label="Por confirmar" value={data?.metrics.pending ?? "—"} detail="pagamentos pendentes" tone="gold"/>
          <Metric icon={<BadgeCheck/>} label="Acessos ativos" value={data?.metrics.active ?? "—"} detail="testes e subscrições" tone="blue"/>
          <Metric icon={<CreditCard/>} label="Receita confirmada" value={data ? `${data.metrics.revenue.toLocaleString("pt-PT")} MT` : "—"} detail="total acumulado" tone="green"/>
        </section>

        <section className="split-grid">
          <article id="pagamentos" className="panel-card span-wide">
            <div className="panel-heading"><div><p className="eyebrow">Prioridade</p><h2>Pagamentos por confirmar</h2></div><button className="secondary-button" disabled={!data?.contacts.length} onClick={() => setModal("payment")}><Plus/>Registar pagamento</button></div>
            {!data ? <Loading/> : data.pendingPayments.length === 0 ? <Empty text="Nenhum pagamento aguarda confirmação."/> : (
              <div className="table-scroll"><table><thead><tr><th>Cliente</th><th>Plano</th><th>Transação</th><th>Valor</th><th/></tr></thead><tbody>{data.pendingPayments.map(payment => <tr key={payment.id}><td><strong>{payment.contacts.name}</strong><small>{payment.contacts.phone}</small></td><td>{payment.plan}</td><td>{payment.transaction_ref}</td><td>{payment.amount.toLocaleString("pt-PT")} MT</td><td><button className="primary-button small" disabled={busy} onClick={() => void confirmPayment(payment.id)}>Confirmar</button></td></tr>)}</tbody></table></div>
            )}
          </article>

          <article className="panel-card merchant-card"><div className="status-dot"/><p className="eyebrow">Método de pagamento</p><h2>Pay IZI via e-Mola</h2><p>Os dados do comerciante serão inseridos assim que estiverem disponíveis.</p><span className="status-pill">Configuração pendente</span></article>

          <article id="contactos" className="panel-card span-wide">
            <div className="panel-heading"><div><p className="eyebrow">Carteira comercial</p><h2>Contactos recentes</h2></div></div>
            {!data ? <Loading/> : data.contacts.length === 0 ? <Empty text="Registe o primeiro contacto para iniciar a operação."/> : (
              <div className="table-scroll"><table><thead><tr><th>Contacto</th><th>País</th><th>Interesse</th><th>Estado</th><th/></tr></thead><tbody>{data.contacts.map(contact => <tr key={contact.id}><td><strong>{contact.name}</strong><small>{contact.email}</small></td><td>{contact.country}</td><td>{contact.interest}</td><td><span className={`lifecycle ${contact.lifecycle}`}>{contact.lifecycle}</span></td><td>{contact.lifecycle === "lead" && <button className="secondary-button small" disabled={busy} onClick={() => void activateTrial(contact.id)}>Teste 48h</button>}</td></tr>)}</tbody></table></div>
            )}
          </article>

          <article id="subscricoes" className="panel-card"><div className="panel-heading"><div><p className="eyebrow">Acessos</p><h2>Subscrições ativas</h2></div></div>{!data ? <Loading/> : data.activeSubscriptions.length === 0 ? <Empty text="Ainda não existem acessos ativos."/> : <div className="subscription-list">{data.activeSubscriptions.slice(0, 8).map(subscription => <div className="subscription-row" key={subscription.id}><span>{subscription.contacts.name}<small>{subscription.plan}</small></span><time>{formatDate(subscription.ends_at)}</time></div>)}</div>}</article>

          <article className="panel-card"><div className="panel-heading"><div><p className="eyebrow">Rastreabilidade</p><h2>Atividade dos agentes</h2></div></div>{!data ? <Loading/> : data.activity.length === 0 ? <Empty text="As ações dos agentes aparecerão aqui."/> : <div className="activity-list">{data.activity.slice(0, 8).map(item => <div className="activity-row" key={item.id}><span className="activity-icon"><Sparkles/></span><span><strong>{item.action}</strong><small>{item.detail}</small></span></div>)}</div>}</article>
        </section>
      </section>

      {modal === "contact" && <Modal title="Registar contacto" description="Adicione um potencial assinante à carteira comercial." close={() => setModal(null)}><form onSubmit={submitContact} className="form-stack"><div className="field-grid"><Field label="Nome" name="name"/><Field label="Email" name="email" type="email"/><Field label="WhatsApp" name="phone"/><Field label="País" name="country" defaultValue="Moçambique"/><Field label="Principal interesse" name="interest" wide/></div><button className="primary-button" type="submit" disabled={busy}>Guardar contacto</button></form></Modal>}
      {modal === "payment" && <Modal title="Registar pagamento" description="Registe a referência antes de confirmar no Pay IZI." close={() => setModal(null)}><form onSubmit={submitPayment} className="form-stack"><SelectContact contacts={data?.contacts ?? []}/><label className="form-field"><span>Plano</span><select name="plan" required defaultValue=""><option value="" disabled>Selecione</option>{Object.entries(PLAN_PRICES).map(([plan, price]) => <option key={plan} value={plan}>{plan} — {price.toLocaleString("pt-PT")} MT</option>)}</select></label><Field label="Número da transação" name="transactionRef"/><Field label="Telefone pagador" name="payerPhone"/><button className="primary-button" type="submit" disabled={busy}>Guardar para validação</button></form></Modal>}
    </main>
  );
}

function Modal({ title, description, children, close }: { title: string; description: string; children: ReactNode; close: () => void }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close" onClick={close} aria-label="Fechar"><X/></button><p className="eyebrow">Briefing Diário</p><h2 id="modal-title">{title}</h2><p>{description}</p>{children}</section></div>;
}

function Field({ label, name, type = "text", defaultValue, wide = false }: { label: string; name: string; type?: string; defaultValue?: string; wide?: boolean }) {
  return <label className={`form-field ${wide ? "wide" : ""}`}><span>{label}</span><input name={name} type={type} defaultValue={defaultValue} required/></label>;
}

function SelectContact({ contacts }: { contacts: Contact[] }) {
  return <label className="form-field"><span>Contacto</span><select name="contactId" required defaultValue=""><option value="" disabled>Selecione</option>{contacts.map(contact => <option key={contact.id} value={contact.id}>{contact.name}</option>)}</select></label>;
}

function Metric({ icon, label, value, detail, tone = "navy" }: { icon: ReactNode; label: string; value: ReactNode; detail: string; tone?: string }) {
  return <article className={`metric-card ${tone}`}><span className="metric-icon">{icon}</span><span><small>{label}</small><strong>{value}</strong><em>{detail}</em></span></article>;
}

function Empty({ text }: { text: string }) { return <div className="empty-state"><span>BD</span><p>{text}</p></div>; }
function Loading() { return <div className="loading-state"><RefreshCw className="spin"/>A carregar…</div>; }
