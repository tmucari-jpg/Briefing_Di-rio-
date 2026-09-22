-- Briefing Diário: estrutura inicial da área administrativa.
-- Execute todo este ficheiro no SQL Editor de um projeto Supabase novo.

create table if not exists public.contacts (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 2 and 120),
  email text not null,
  phone text not null,
  country text not null default 'Moçambique',
  interest text not null default 'Informação empresarial',
  lifecycle text not null default 'lead' check (lifecycle in ('lead', 'trial', 'active')),
  created_at timestamptz not null default now()
);

create unique index if not exists contacts_email_lower_idx on public.contacts (lower(email));

create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid not null references public.contacts(id) on delete restrict,
  plan text not null check (plan in ('Semanal', 'Mensal', 'Trimestral', 'Semestral', 'Anual')),
  amount integer not null check (amount in (92, 250, 700, 1250, 2500)),
  transaction_ref text not null unique,
  payer_phone text not null,
  status text not null default 'pending' check (status in ('pending', 'confirmed', 'rejected')),
  confirmed_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists payments_contact_id_idx on public.payments(contact_id);
create index if not exists payments_status_idx on public.payments(status);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid not null references public.contacts(id) on delete restrict,
  payment_id uuid unique references public.payments(id) on delete restrict,
  plan text not null check (plan in ('Teste gratuito', 'Semanal', 'Mensal', 'Trimestral', 'Semestral', 'Anual')),
  amount integer not null check (amount >= 0),
  starts_at timestamptz not null,
  ends_at timestamptz not null check (ends_at > starts_at),
  created_at timestamptz not null default now()
);

create index if not exists subscriptions_contact_id_idx on public.subscriptions(contact_id);
create index if not exists subscriptions_ends_at_idx on public.subscriptions(ends_at);

create table if not exists public.agent_activity (
  id uuid primary key default gen_random_uuid(),
  agent text not null,
  action text not null,
  detail text not null,
  created_at timestamptz not null default now()
);

-- Os projetos Supabase mais recentes não expõem automaticamente tabelas novas.
grant usage on schema public to authenticated;
grant select, insert, update on public.contacts to authenticated;
grant select, insert, update on public.payments to authenticated;
grant select, insert, update on public.subscriptions to authenticated;
grant select, insert on public.agent_activity to authenticated;

alter table public.contacts enable row level security;
alter table public.payments enable row level security;
alter table public.subscriptions enable row level security;
alter table public.agent_activity enable row level security;

-- Camada adicional para eventual acesso direto pelo cliente autenticado.
-- A aplicação atual executa mutações em rotas protegidas no servidor.
create policy "admin_contacts" on public.contacts for all to authenticated
  using (lower((select auth.jwt() ->> 'email')) = 'geral.amsol@gmail.com')
  with check (lower((select auth.jwt() ->> 'email')) = 'geral.amsol@gmail.com');

create policy "admin_payments" on public.payments for all to authenticated
  using (lower((select auth.jwt() ->> 'email')) = 'geral.amsol@gmail.com')
  with check (lower((select auth.jwt() ->> 'email')) = 'geral.amsol@gmail.com');

create policy "admin_subscriptions" on public.subscriptions for all to authenticated
  using (lower((select auth.jwt() ->> 'email')) = 'geral.amsol@gmail.com')
  with check (lower((select auth.jwt() ->> 'email')) = 'geral.amsol@gmail.com');

create policy "admin_activity" on public.agent_activity for all to authenticated
  using (lower((select auth.jwt() ->> 'email')) = 'geral.amsol@gmail.com')
  with check (lower((select auth.jwt() ->> 'email')) = 'geral.amsol@gmail.com');
