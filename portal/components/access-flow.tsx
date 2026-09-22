"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Mail, MessageCircle, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

type Channel = "email" | "whatsapp";

export function AccessFlow() {
  const router = useRouter();
  const [channel, setChannel] = useState<Channel>("email");
  const [step, setStep] = useState<"details" | "code">("details");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function requestCode(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    if (name.trim().length < 2) return setMessage("Indique o seu nome.");
    if (channel === "whatsapp") return setMessage("O envio por WhatsApp será ativado quando ligarmos a API. Por enquanto, escolha email.");
    if (!email.trim()) return setMessage("Indique um email válido.");

    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim().toLowerCase(),
      options: { shouldCreateUser: true },
    });
    setLoading(false);
    if (error) return setMessage(error.message);
    setStep("code");
    setMessage("Enviámos um código de acesso para o seu email.");
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    if (!/^\d{6,8}$/.test(code.trim())) return setMessage("Introduza o código recebido.");

    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.verifyOtp({
      email: email.trim().toLowerCase(),
      token: code.trim(),
      type: "email",
    });

    if (error) {
      setLoading(false);
      return setMessage("Código inválido ou expirado. Solicite um novo código.");
    }

    const response = await fetch("/api/onboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), email: email.trim().toLowerCase(), phone: phone.trim() || null, preferredChannel: channel }),
    });
    const result = (await response.json()) as { error?: string };
    setLoading(false);
    if (!response.ok) return setMessage(result.error ?? "Não foi possível ativar o acesso.");
    router.push("/leitor");
    router.refresh();
  }

  return (
    <div>
      <p className="eyebrow">ÁREA DO ASSINANTE</p>
      <h2>{step === "details" ? "Como quer receber o acesso?" : "Confirme o seu código"}</h2>
      <p className="muted">{step === "details" ? "Escolha o canal mais conveniente. Não precisa criar uma palavra-passe." : `Introduza o código enviado para ${email}.`}</p>

      {step === "details" ? (
        <form onSubmit={requestCode}>
          <div className="channel-grid">
            <button type="button" className={`channel ${channel === "email" ? "selected" : ""}`} onClick={() => setChannel("email")}>
              <Mail size={21} /><span><strong>Email</strong><small>Disponível agora</small></span>
            </button>
            <button type="button" className={`channel ${channel === "whatsapp" ? "selected" : ""}`} onClick={() => setChannel("whatsapp")}>
              <MessageCircle size={21} /><span><strong>WhatsApp</strong><small>API em configuração</small></span>
            </button>
          </div>
          <label>Nome<input value={name} onChange={(event) => setName(event.target.value)} placeholder="O seu nome" autoComplete="name" /></label>
          {channel === "email" ? (
            <label>Email<input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="nome@exemplo.com" type="email" autoComplete="email" /></label>
          ) : (
            <label>Número de WhatsApp<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+258 84 000 0000" type="tel" autoComplete="tel" /></label>
          )}
          <button className="primary-button" disabled={loading} type="submit">{loading ? "A enviar…" : "Receber código"}{!loading && <ArrowRight size={18} />}</button>
        </form>
      ) : (
        <form onSubmit={verifyCode}>
          <label>Código de acesso<input className="otp-input" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} placeholder="000000" inputMode="numeric" autoComplete="one-time-code" maxLength={8} /></label>
          <button className="primary-button" disabled={loading} type="submit">{loading ? "A confirmar…" : "Confirmar e entrar"}{!loading && <ArrowRight size={18} />}</button>
          <button className="text-button" type="button" onClick={() => { setStep("details"); setCode(""); setMessage(""); }}>Alterar email</button>
        </form>
      )}
      {message && <p className="form-message" role="status">{message}</p>}
      <div className="secure-note"><ShieldCheck size={17} /><span>O código serve apenas para entrar no Briefing Diário.</span></div>
    </div>
  );
}
