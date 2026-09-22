-- Briefing Diário: estrutura da área administrativa e do portal.

create table if not exists public.contacts (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 2 and 120),
  email text,
  phone text,
  country text not null default 'Moçambique',
  interest text not null default 'Informação empresarial',
  lifecycle text not null default 'lead' check (lifecycle in ('lead', 'trial', 'active')),
  auth_user_id uuid unique references auth.users(id) on delete set null,
  preferred_channel text not null default 'email' check (preferred_channel in ('email', 'whatsapp')),
  verified_at timestamptz,
  trial_started_at timestamptz,
  constraint contacts_reachable_check check (
    nullif(btrim(coalesce(email, '')), '') is not null
    or nullif(btrim(coalesce(phone, '')), '') is not null
  ),
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
  payment_method text not null default 'emola_payizi' check (payment_method in ('emola_payizi', 'mpesa', 'emola', 'card')),
  provider text not null default 'manual' check (provider in ('manual', 'paysuite')),
  provider_payment_id text unique,
  checkout_url text,
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
create unique index if not exists subscriptions_one_trial_per_contact_idx
  on public.subscriptions(contact_id) where plan = 'Teste gratuito';

create table if not exists public.agent_activity (
  id uuid primary key default gen_random_uuid(),
  agent text not null,
  action text not null,
  detail text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.briefings (
  id uuid primary key default gen_random_uuid(),
  language text not null check (language in ('pt', 'en')),
  edition_date date not null default (now() at time zone 'Africa/Maputo')::date,
  payload jsonb not null,
  published_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (language, edition_date)
);

create index if not exists briefings_published_at_idx on public.briefings(published_at desc);

grant usage on schema public to authenticated;
grant select, insert, update on public.contacts, public.payments, public.subscriptions to authenticated;
grant select, insert on public.agent_activity to authenticated;
grant select on public.briefings to authenticated;
grant all on public.contacts, public.payments, public.subscriptions, public.briefings to service_role;
revoke all on public.briefings from anon;

alter table public.contacts enable row level security;
alter table public.payments enable row level security;
alter table public.subscriptions enable row level security;
alter table public.agent_activity enable row level security;
alter table public.briefings enable row level security;

create policy "contacts_admin_or_owner_select" on public.contacts for select to authenticated
  using (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com' or auth_user_id = (select auth.uid()));
create policy "contacts_admin_insert" on public.contacts for insert to authenticated
  with check (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com');
create policy "contacts_admin_update" on public.contacts for update to authenticated
  using (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com')
  with check (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com');

create policy "payments_admin_or_owner_select" on public.payments for select to authenticated
  using (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com' or exists (
    select 1 from public.contacts c where c.id = payments.contact_id and c.auth_user_id = (select auth.uid())
  ));
create policy "payments_admin_insert" on public.payments for insert to authenticated
  with check (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com');
create policy "payments_admin_update" on public.payments for update to authenticated
  using (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com')
  with check (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com');

create policy "subscriptions_admin_or_owner_select" on public.subscriptions for select to authenticated
  using (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com' or exists (
    select 1 from public.contacts c where c.id = subscriptions.contact_id and c.auth_user_id = (select auth.uid())
  ));
create policy "subscriptions_admin_insert" on public.subscriptions for insert to authenticated
  with check (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com');
create policy "subscriptions_admin_update" on public.subscriptions for update to authenticated
  using (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com')
  with check (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com');

create policy "admin_activity" on public.agent_activity for all to authenticated
  using (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com')
  with check (lower((select auth.jwt()) ->> 'email') = 'geral.amsol@gmail.com');

create policy "active_subscribers_read_briefings" on public.briefings for select to authenticated
  using (exists (
    select 1 from public.subscriptions s
    join public.contacts c on c.id = s.contact_id
    where c.auth_user_id = (select auth.uid())
      and s.starts_at <= now()
      and s.ends_at > now()
  ));
