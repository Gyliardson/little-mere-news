import type { Metadata } from "next";
import { Inter, Montserrat } from "next/font/google";
import "../globals.css";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import Link from "next/link";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const montserrat = Montserrat({
  variable: "--font-montserrat",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    template: "%s | Little Mere News",
    default: "Little Mere News - Big tech insights from a Little Mere.",
  },
  description: "Daily insights and news on AI, Gaming, and Dev, curated from the best sources.",
  icons: {
    icon: '/favicon.ico',
  }
};

export async function generateStaticParams() {
  return [{ lang: "en" }, { lang: "pt" }];
}

export default async function RootLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}>) {
  const { lang } = await params;
  return (
    <html
      lang={lang}
      className={`${inter.variable} ${montserrat.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[var(--color-background)] text-[var(--color-foreground)]">
        <header className="border-b border-primary/20 bg-background-secondary p-4 sticky top-0 z-50 shadow-md">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <Link href={`/${lang}`} className="flex items-center gap-3 group">
              <img src="/logo.png" alt="Little Mere News Logo" className="w-10 h-10 object-contain group-hover:scale-105 transition-transform" />
              <div>
                <h1 className="text-xl font-bold tracking-tight group-hover:text-accent transition-colors">Little Mere News</h1>
                <p className="text-xs text-foreground-muted hidden sm:block">
                  Big tech insights from a <span className="text-accent font-medium">Little Mere</span>.
                </p>
              </div>
            </Link>
            <nav aria-label="Main Navigation">
              <LanguageSwitcher />
            </nav>
          </div>
        </header>

        <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-8">
          {children}
        </main>

        <footer className="border-t border-primary/20 bg-background-secondary p-6 mt-auto">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-foreground-muted">
              © {new Date().getFullYear()} Little Mere News. All rights reserved.
            </p>
            <nav aria-label="Footer Navigation" className="flex gap-4 text-sm text-foreground-muted">
              <Link href={`/${lang}/privacy`} className="hover:text-accent transition-colors">Privacy Policy</Link>
              <Link href={`/${lang}/terms`} className="hover:text-accent transition-colors">Terms of Service</Link>
              <Link href={`/${lang}/contact`} className="hover:text-accent transition-colors">Contact</Link>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
