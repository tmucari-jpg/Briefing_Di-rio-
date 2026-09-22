"use client";

import { FormEvent, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { PLAN_PRICES, type PaidPlan } from "@/lib/plans";

const plans = Object.entries(PLAN_PRICES) as [PaidPlan, number][];

export function PaymentForm() {
  const [plan, setPlan] = useState<PaidPlan>("Mensal");
  const [phone, setPhone] = useState("");
  const [reference, setReference] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);

  async function submitPayment(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setMessage(""); setSuccess(false);
    const response = await fetch("/api/payment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan, payerPhone: phone, transactionRef: reference }),
    });
    const result = (await response.json()) as { error?: string };
    setLoading(false);
    if (!response.ok) return setMessage(result.error ?? "Não foi possível registar o pagamento.");
    setSuccess(true);
    setMessage("Pagamento registado. O acesso será ativado após a confirmação.");
    setReference("");
  }

  return (
    <section className="payment-card" id="planos">
      <div><p className="eyebrow">CONTINUAR COM ACESSO</p><h2>Escolha o seu plano</h2><p className="muted">Pagamento Pay IZI através do e-Mola. O gateway automático será acrescentado posteriormente.</p></div>
      <form onSubmit={submitPayment}>
        <div className="plans-grid">
          {plans.map(([name, price]) => (
            <button type="button" className={`plan-option ${plan === name ? "selected" : ""}`} key={name} onClick={() => setPlan(name)}><span>{name}</span><strong>{price.toLocaleString("pt-MZ")} MT</strong></button>
          ))}
        </div>
        <div className="merchant-box"><strong>Pay IZI — e-Mola</strong><span>Comerciante: confirme o número/código indicado pela AMSOL antes do pagamento.</span></div>
        <div className="two-columns">
          <label>Número que efetuou o pagamento<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+258 86 000 0000" type="tel" required /></label>
          <label>Referência da transação<input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Ex.: TX123456" required /></label>
        </div>
        <button className="primary-button" disabled={loading} type="submit">{loading ? "A registar…" : `Registar pagamento de ${PLAN_PRICES[plan].toLocaleString("pt-MZ")} MT`}</button>
      </form>
      {message && <p className={`form-message ${success ? "success" : ""}`}>{success && <CheckCircle2 size={17} />}{message}</p>}
    </section>
  );
}
