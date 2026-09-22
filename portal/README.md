# Briefing Diário — Portal do Assinante

Aplicação Next.js independente para o acesso dos assinantes. Usa o mesmo projeto Supabase do painel administrativo.

## Variáveis de ambiente

Configure no projeto Vercel do portal:

```env
NEXT_PUBLIC_SUPABASE_URL=https://jteamrgobvvwqwwyuqik.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
```

`SUPABASE_SERVICE_ROLE_KEY` é privada e nunca deve receber o prefixo `NEXT_PUBLIC_`.

## Vercel

- Root Directory: `portal`
- Framework Preset: Next.js
- Build Command: `npm run build`
- Output Directory: deixar vazio
- Install Command: `npm install`

## Funcionalidades

- Entrada sem palavra-passe por OTP de email.
- Estrutura visual preparada para WhatsApp OTP.
- Teste gratuito único de 48 horas.
- Bloqueio automático quando a subscrição termina.
- Planos semanal, mensal, trimestral, semestral e anual.
- Registo manual de pagamento Pay IZI/e-Mola.
- Área protegida para notícias e oportunidades completas.
- Estrutura preparada para gateway automático PaySuite.

## Configuração do email OTP

No Supabase, altere o modelo de Magic Link para apresentar `{{ .Token }}`. Assim, o utilizador recebe um código em vez de depender de uma palavra-passe.
