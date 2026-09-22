export const PLAN_PRICES = {
  Semanal: 92,
  Mensal: 250,
  Trimestral: 700,
  Semestral: 1250,
  Anual: 2500,
} as const;

export type PaidPlan = keyof typeof PLAN_PRICES;

export function isPaidPlan(value: unknown): value is PaidPlan {
  return typeof value === "string" && value in PLAN_PRICES;
}
