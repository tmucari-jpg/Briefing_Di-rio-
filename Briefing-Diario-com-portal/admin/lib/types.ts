export type Contact = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  country: string;
  interest: string;
  lifecycle: "lead" | "trial" | "active";
  auth_user_id: string | null;
  preferred_channel: "email" | "whatsapp";
  verified_at: string | null;
  trial_started_at: string | null;
  created_at: string;
};

export type Payment = {
  id: string;
  contact_id: string;
  plan: string;
  amount: number;
  transaction_ref: string;
  payer_phone: string;
  status: "pending" | "confirmed" | "rejected";
  created_at: string;
  confirmed_at: string | null;
  payment_method: "emola_payizi" | "mpesa" | "emola" | "card";
  provider: "manual" | "paysuite";
  provider_payment_id: string | null;
  checkout_url: string | null;
  contacts: Contact;
};

export type Subscription = {
  id: string;
  contact_id: string;
  plan: string;
  amount: number;
  starts_at: string;
  ends_at: string;
  contacts: Contact;
};

export type AgentActivity = {
  id: string;
  agent: string;
  action: string;
  detail: string;
  created_at: string;
};

export type Overview = {
  contacts: Contact[];
  pendingPayments: Payment[];
  activeSubscriptions: Subscription[];
  activity: AgentActivity[];
  metrics: { contacts: number; pending: number; active: number; revenue: number };
  merchant: { status: "pending" | "configured"; label: string };
};
