"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { LockKeyhole, Mail } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

export default function LoginForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim().toLowerCase();
    const password = String(form.get("password") ?? "");
    try {
      const supabase = createClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
      if (signInError) throw signInError;
      router.replace("/");
      router.refresh();
    } catch {
      setError("Email ou palavra-passe incorretos.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="login-brand"><span className="logo-symbol">BD</span><span><strong>Briefing</strong><br/>Diário</span></div>
        <p className="eyebrow">Área administrativa</p>
        <h1>Entre no centro de operações</h1>
        <p className="login-copy">Acompanhe contactos, testes, pagamentos e subscrições num único lugar.</p>
        <form onSubmit={submit} className="login-form">
          <label><span>Email</span><div className="input-wrap"><Mail/><input name="email" type="email" autoComplete="email" required placeholder="geral.amsol@gmail.com"/></div></label>
          <label><span>Palavra-passe</span><div className="input-wrap"><LockKeyhole/><input name="password" type="password" autoComplete="current-password" minLength={8} required/></div></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={busy}>{busy ? "A entrar…" : "Entrar"}</button>
        </form>
        <small>Acesso reservado à administração do Briefing Diário.</small>
      </section>
    </main>
  );
}
