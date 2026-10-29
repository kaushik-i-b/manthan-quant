import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "MANTHAN QUANT Terminal", description: "Autonomous AI trading terminal" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-bg text-ink">{children}</body>
    </html>
  );
}
