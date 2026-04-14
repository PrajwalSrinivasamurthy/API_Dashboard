import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-geist-sans",
});

export const metadata: Metadata = {
  title: "Project LLM — Dashboard",
  description: "Project keys and OpenAI usage from the proxy API",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      {/* Inline fallbacks so background/text stay correct if a CSS chunk fails to load */}
      <body
        className={`${inter.className} min-h-screen antialiased`}
        style={{
          backgroundColor: "var(--bg, #0c0e12)",
          color: "var(--text, #e8eaef)",
        }}
      >
        {children}
      </body>
    </html>
  );
}
