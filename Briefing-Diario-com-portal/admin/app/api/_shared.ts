import { NextResponse } from "next/server";
import { getAdmin } from "@/lib/auth";

export async function requireApiAdmin() {
  return getAdmin();
}

export function unauthorized() {
  return NextResponse.json({ error: "Acesso não autorizado." }, { status: 401 });
}

export function serverError(message: string, error: unknown) {
  console.error(message, error);
  return NextResponse.json({ error: "Não foi possível concluir a operação." }, { status: 500 });
}
