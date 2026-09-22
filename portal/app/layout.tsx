import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Briefing Diário — Área do Assinante",
  description: "Notícias, contexto e oportunidades para decisões melhores.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt"><body>{children}</body></html>;
}
