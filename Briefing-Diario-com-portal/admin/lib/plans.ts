export const PLAN_PRICES = {
  Semanal: 92,
  Mensal: 250,
  Trimestral: 700,
  Semestral: 1250,
  Anual: 2500,
} as const;

export type PaidPlan = keyof typeof PLAN_PRICES;

export function addPlanDuration(start: Date, plan: PaidPlan) {
  if (plan === "Semanal") return new Date(start.getTime() + 7 * 86_400_000);
  const months = { Mensal: 1, Trimestral: 3, Semestral: 6, Anual: 12 }[plan];
  const result = new Date(start);
  const originalDay = result.getUTCDate();
  result.setUTCDate(1);
  result.setUTCMonth(result.getUTCMonth() + months);
  const lastDay = new Date(Date.UTC(result.getUTCFullYear(), result.getUTCMonth() + 1, 0)).getUTCDate();
  result.setUTCDate(Math.min(originalDay, lastDay));
  return result;
}

export function isPaidPlan(value: unknown): value is PaidPlan {
  return typeof value === "string" && value in PLAN_PRICES;
}
