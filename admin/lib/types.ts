export type Contact = {
  id: string;
  name: string;
  email: string;
  phone: string;
  country: string;
  interest: string;
  lifecycle: "lead" | "trial" | "active";
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
