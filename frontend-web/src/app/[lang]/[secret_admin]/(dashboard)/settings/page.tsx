import { getAdminContext } from "@/lib/auth/admin";
import { User, Database, ShieldCheck, Server } from "lucide-react";

const t = {
  pt: {
    title: "Configurações",
    subtitle: "Visualize seu perfil e o estado observado do sistema.",
    profileSection: "Perfil do Administrador",
    emailLabel: "Email de Acesso",
    emailConfirmed: "Email confirmado",
    emailUnconfirmed: "Email não confirmado",
    roleLabel: "Autorização",
    adminRole: "Administrador autorizado",
    systemSection: "Informações do Sistema",
    versionLabel: "Versão do Painel",
    dbStatusLabel: "Status do Banco de Dados",
    dbStatusConnected: "Consulta disponível",
    dbStatusUnavailable: "Consulta indisponível",
    totalNewsLabel: "Total de Notícias (Banco)",
    obscurityLabel: "Obscuridade da URL administrativa",
    obscurityValue: "Redução opcional de ruído",
    obscurityNote: "Não é autenticação nem autorização. O acesso real depende de Auth + autorização no servidor + RLS.",
  },
  en: {
    title: "Settings",
    subtitle: "View your profile and the observed system state.",
    profileSection: "Administrator Profile",
    emailLabel: "Login Email",
    emailConfirmed: "Email confirmed",
    emailUnconfirmed: "Email not confirmed",
    roleLabel: "Authorization",
    adminRole: "Authorized administrator",
    systemSection: "System Information",
    versionLabel: "Panel Version",
    dbStatusLabel: "Database Status",
    dbStatusConnected: "Query available",
    dbStatusUnavailable: "Query unavailable",
    totalNewsLabel: "Total News (Database)",
    obscurityLabel: "Administrative URL obscurity",
    obscurityValue: "Optional noise reduction",
    obscurityNote: "This is not authentication or authorization. Real access depends on Auth + server authorization + RLS.",
  },
};

export default async function SettingsPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  const labels = lang === "pt" ? t.pt : t.en;
  const { supabase, user, isAdmin } = await getAdminContext();
  const { count: totalNews, error: countError } = await supabase
    .from("news")
    .select("*", { count: "exact", head: true });

  const dbAvailable = !countError;
  const emailConfirmed = Boolean(user?.email_confirmed_at);

  return (
    <div className="space-y-8 pb-12 max-w-4xl">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">{labels.title}</h1>
        <p className="text-foreground-muted">{labels.subtitle}</p>
      </header>

      <div className="space-y-8">
        <section className="bg-background-secondary border border-primary/20 rounded-2xl overflow-hidden">
          <div className="p-6 border-b border-primary/20 bg-background/50">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
              <User className="w-5 h-5 text-accent" />
              {labels.profileSection}
            </h2>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <p className="block text-sm font-medium text-foreground-muted mb-2">{labels.emailLabel}</p>
              <div className="px-4 py-3 bg-background border border-primary/10 rounded-xl text-foreground font-medium flex flex-wrap items-center justify-between gap-2">
                <span>{user?.email || "—"}</span>
                <span className="px-2 py-1 bg-accent/10 text-accent text-xs font-bold rounded-md">
                  {emailConfirmed ? labels.emailConfirmed : labels.emailUnconfirmed}
                </span>
              </div>
            </div>
            <div>
              <p className="block text-sm font-medium text-foreground-muted mb-2">{labels.roleLabel}</p>
              <div className="px-4 py-3 bg-background border border-primary/10 rounded-xl text-foreground font-medium">
                {isAdmin ? labels.adminRole : "—"}
              </div>
            </div>
          </div>
        </section>

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
                  <div className="p-2 bg-primary/10 rounded-lg"><ShieldCheck className="w-5 h-5 text-primary" /></div>
                  <h3 className="text-sm font-medium text-foreground-muted">{labels.obscurityLabel}</h3>
                </div>
                <p className="text-lg font-bold text-foreground mt-2">{labels.obscurityValue}</p>
                <p className="text-sm text-foreground-muted mt-2 leading-relaxed">{labels.obscurityNote}</p>
              </div>
              <div className="p-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 bg-primary/10 rounded-lg"><Database className="w-5 h-5 text-primary" /></div>
                  <h3 className="text-sm font-medium text-foreground-muted">{labels.dbStatusLabel}</h3>
                </div>
                <p className="text-xl font-bold text-foreground mt-2 flex items-center gap-2" role="status">
                  <span className={`w-2 h-2 rounded-full ${dbAvailable ? "bg-green-400" : "bg-red-400"}`} aria-hidden="true" />
                  {dbAvailable ? labels.dbStatusConnected : labels.dbStatusUnavailable}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-primary/10 border-t border-primary/10">
              <div className="p-6">
                <h3 className="text-sm font-medium text-foreground-muted mb-2">{labels.versionLabel}</h3>
                <p className="text-xl font-bold text-foreground">v0.1.0-beta</p>
              </div>
              <div className="p-6">
                <h3 className="text-sm font-medium text-foreground-muted mb-2">{labels.totalNewsLabel}</h3>
                <p className="text-xl font-bold text-foreground">{dbAvailable ? totalNews ?? 0 : "—"}</p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
