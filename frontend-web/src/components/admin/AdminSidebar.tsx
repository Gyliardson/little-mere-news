"use client";

import Link from "next/link";
import { LayoutDashboard, FileText, Settings, LogOut, Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";
import { useState } from "react";

const t = {
  pt: {
    overview: "Visão Geral",
    manageNews: "Gerenciar Notícias",
    settings: "Configurações",
    logout: "Sair",
  },
  en: {
    overview: "Overview",
    manageNews: "Manage News",
    settings: "Settings",
    logout: "Logout",
  },
};

export default function AdminSidebar({ lang, secret_admin }: { lang: string, secret_admin: string }) {
  const basePath = `/${lang}/${secret_admin}`;
  const pathname = usePathname();
  const router = useRouter();
  const isPt = pathname.startsWith("/pt");
  const labels = isPt ? t.pt : t.en;
  const [loggingOut, setLoggingOut] = useState(false);

  const toggleLanguage = () => {
    const newPath = isPt
      ? pathname.replace(/^\/pt/, "/en")
      : pathname.replace(/^\/en/, "/pt");
    window.location.href = newPath;
  };

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      const supabase = createBrowserSupabaseClient();
      await supabase.auth.signOut();
      router.push(`/${lang}/${secret_admin}/login`);
      router.refresh();
    } catch {
      setLoggingOut(false);
    }
  };

  const isActive = (path: string) => {
    if (path === basePath) {
      return pathname === basePath || pathname === `${basePath}/`;
    }
    return pathname.startsWith(path);
  };

  const linkClass = (path: string) =>
    `flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
      isActive(path)
        ? "text-accent bg-accent/10 border border-accent/20"
        : "text-foreground-muted hover:text-foreground hover:bg-primary/10"
    }`;

  return (
    <aside className="w-64 shrink-0 bg-background-secondary border-r border-primary/20 flex flex-col h-full">
      <div className="p-6 border-b border-primary/20 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-accent">LMN Admin</h2>
          <p className="text-xs text-foreground-muted mt-1">Phantom Mode</p>
        </div>
        <button
          onClick={toggleLanguage}
          className="px-2 py-1 rounded-md border border-primary/30 hover:border-accent hover:bg-accent/10 transition-colors text-xs font-bold uppercase tracking-wider"
          aria-label="Toggle Language"
        >
          {isPt ? "EN" : "PT"}
        </button>
      </div>

      <nav className="flex-1 p-4 space-y-2">
        <Link 
          href={basePath}
          className={linkClass(basePath)}
        >
          <LayoutDashboard className="w-5 h-5" />
          <span className="font-medium">{labels.overview}</span>
        </Link>
        <Link 
          href={`${basePath}/news`}
          className={linkClass(`${basePath}/news`)}
        >
          <FileText className="w-5 h-5" />
          <span className="font-medium">{labels.manageNews}</span>
        </Link>
        <Link 
          href={`${basePath}/settings`}
          className={linkClass(`${basePath}/settings`)}
        >
          <Settings className="w-5 h-5" />
          <span className="font-medium">{labels.settings}</span>
        </Link>
      </nav>

      <div className="p-4 border-t border-primary/20">
        <button
          onClick={handleLogout}
          disabled={loggingOut}
          className="flex items-center gap-3 px-4 py-3 w-full rounded-xl text-red-400 hover:text-red-300 hover:bg-red-400/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loggingOut ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <LogOut className="w-5 h-5" />
          )}
          <span className="font-medium">{labels.logout}</span>
        </button>
      </div>
    </aside>
  );
}
