import type { Metadata } from "next";
import Link from "next/link";
import localFont from "next/font/local";
import { AppNav } from "@/components/AppNav";
import "./globals.css";

const plexSans = localFont({
  src: "../fonts/IBMPlexSans-Variable.woff2",
  weight: "100 900",
  style: "normal",
  display: "swap",
  variable: "--font-plex-sans",
});

const plexMono = localFont({
  src: [
    { path: "../fonts/IBMPlexMono-Regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/IBMPlexMono-Medium.woff2", weight: "500", style: "normal" },
  ],
  display: "swap",
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "SportAnalyst — model vs market",
  description:
    "Football match probabilities compared against bookmaker odds, from free data only.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body className="min-h-screen bg-canvas font-sans text-ink antialiased">
        <div className="flex min-h-screen">
          <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r border-white/[0.07] bg-shell lg:flex">
            <div className="px-6 pb-7 pt-7">
              <Link href="/" className="block">
                <span className="block text-[15px] font-medium tracking-tight text-ink">
                  SportAnalyst
                </span>
                <span className="mt-1 block font-mono text-[11px] text-ink-mute">
                  model vs market
                </span>
              </Link>
            </div>
            <AppNav />
            <div className="mt-auto px-6 py-6">
              <p className="font-mono text-[11px] leading-relaxed text-ink-mute">
                Free data only.
                <br />
                Runs locally.
              </p>
            </div>
          </aside>

          <div className="flex min-w-0 flex-1 flex-col">
            <header className="border-b border-white/[0.07] bg-shell px-5 pb-3 pt-4 lg:hidden">
              <Link href="/" className="text-[15px] font-medium tracking-tight text-ink">
                SportAnalyst
              </Link>
              <AppNav />
            </header>
            <main className="mx-auto w-full max-w-[1440px] flex-1 px-5 py-8 sm:px-8 sm:py-10">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
