import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Briefing Diário — Administração",
  description: "Gestão independente de contactos, pagamentos e subscrições do Briefing Diário.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt"><body>{children}</body></html>;
}
