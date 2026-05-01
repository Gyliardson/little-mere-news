import { createServerSupabaseClient } from "@/lib/supabase/server";
import { supabase as adminSupabase } from "@/lib/supabase/client";
import { User, Database, ShieldCheck, Server } from "lucide-react";

const t = {
  pt: {
    title: "Configurações",
    subtitle: "Gerencie seu perfil e visualize o status do sistema.",
    profileSection: "Perfil do Administrador",
    emailLabel: "Email de Acesso",
    roleLabel: "Nível de Acesso",
    systemSection: "Informações do Sistema",
    versionLabel: "Versão do Painel",
    dbStatusLabel: "Status do Banco de Dados",
    dbStatusConnected: "Conectado",
    totalNewsLabel: "Total de Notícias (Banco)",
    phantomLabel: "Proteção Phantom Route",
    phantomActive: "Ativa",
  },
  en: {
    title: "Settings",
    subtitle: "Manage your profile and view system status.",
    profileSection: "Administrator Profile",
    emailLabel: "Login Email",
    roleLabel: "Access Level",
    systemSection: "System Information",
    versionLabel: "Panel Version",
    dbStatusLabel: "Database Status",
    dbStatusConnected: "Connected",
    totalNewsLabel: "Total News (Database)",
    phantomLabel: "Phantom Route Protection",
    phantomActive: "Active",
  },
};

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const isPt = lang === "pt";
  const labels = isPt ? t.pt : t.en;

  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();

  // Get total news count
  const { count: totalNews } = await adminSupabase
    .from("news")
    .select("*", { count: "exact", head: true });

  return (
    <div className="space-y-8 pb-12 max-w-4xl">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          {labels.title}
        </h1>
        <p className="text-foreground-muted">{labels.subtitle}</p>
      </header>

      <div className="space-y-8">
        {/* Profile Section */}
        <section className="bg-background-secondary border border-primary/20 rounded-2xl overflow-hidden">
          <div className="p-6 border-b border-primary/20 bg-background/50">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
              <User className="w-5 h-5 text-accent" />
              {labels.profileSection}
            </h2>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <label className="block text-sm font-medium text-foreground-muted mb-2">
                {labels.emailLabel}
              </label>
              <div className="px-4 py-3 bg-background border border-primary/10 rounded-xl text-foreground font-medium flex items-center justify-between">
                <span>{user?.email || "Unknown"}</span>
                <span className="px-2 py-1 bg-accent/10 text-accent text-xs font-bold rounded-md">
                  Verified
                </span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground-muted mb-2">
                {labels.roleLabel}
              </label>
              <div className="px-4 py-3 bg-background border border-primary/10 rounded-xl text-foreground font-medium">
                Super Administrator
              </div>
            </div>
          </div>
        </section>

        {/* System Information Section */}
        <section className="bg-background-secondary border border-primary/20 rounded-2xl overflow-hidden">
          <div className="p-6 border-b border-primary/20 bg-background/50">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
              <Server className="w-5 h-5 text-primary" />
              {labels.systemSection}
            </h2>
          </div>
          <div className="p-0">
            <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-primary/10">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <ShieldCheck className="w-5 h-5 text-primary" />
                  </div>
                  <h3 className="text-sm font-medium text-foreground-muted">
                    {labels.phantomLabel}
                  </h3>
                </div>
                <p className="text-xl font-bold text-green-400 mt-2">
                  {labels.phantomActive}
                </p>
              </div>
              <div className="p-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Database className="w-5 h-5 text-primary" />
                  </div>
                  <h3 className="text-sm font-medium text-foreground-muted">
                    {labels.dbStatusLabel}
                  </h3>
                </div>
                <p className="text-xl font-bold text-foreground mt-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                  {labels.dbStatusConnected}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-primary/10 border-t border-primary/10">
              <div className="p-6">
                <h3 className="text-sm font-medium text-foreground-muted mb-2">
                  {labels.versionLabel}
                </h3>
                <p className="text-xl font-bold text-foreground">v0.1.0-beta</p>
              </div>
              <div className="p-6">
                <h3 className="text-sm font-medium text-foreground-muted mb-2">
                  {labels.totalNewsLabel}
                </h3>
                <p className="text-xl font-bold text-foreground">{totalNews}</p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
