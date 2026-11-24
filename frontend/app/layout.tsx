import type { Metadata } from "next";
import Link from "next/link";
import { ClerkProvider, Show, UserButton } from "@clerk/nextjs";
import "./globals.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Contract review", description: "Check a contract against a fixed checklist" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><ClerkProvider>
          <Show when="signed-in">
            <header className="top">
              <Link href="/" className="brand">Contract review</Link>
              <UserButton />
            </header>
          </Show>
          {children}
        </ClerkProvider></body>
    </html>
  );
}
