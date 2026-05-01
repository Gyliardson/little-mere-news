import { createServerSupabaseClient } from "@/lib/supabase/server";
import NewsTable from "@/components/admin/NewsTable";

export const revalidate = 0; // Always fetch fresh data for admin

const t = {
  pt: {
    title: "Gestor de Notícias",
    subtitle: "Revise as publicações processadas pelas VMs (Harvester).",
    total: "artigos no banco",
  },
  en: {
    title: "News Manager",
    subtitle: "Review posts processed by the VMs (Harvester).",
    total: "articles in database",
  },
};

export default async function NewsManager({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const isPt = lang === "pt";
  const labels = isPt ? t.pt : t.en;

  const supabase = await createServerSupabaseClient();

  const { data: news } = await supabase
    .from("news")
    .select("*")
    .order("published_at", { ascending: false });

  const safeNews = news ?? [];

  return (
    <div className="space-y-8 pb-12">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            {labels.title}
          </h1>
          <p className="text-foreground-muted">{labels.subtitle}</p>
        </div>
        <div className="px-4 py-2 bg-background-secondary border border-primary/20 rounded-xl">
          <span className="text-2xl font-bold text-accent">{safeNews.length}</span>
          <span className="text-sm text-foreground-muted ml-2">{labels.total}</span>
        </div>
      </header>

      <NewsTable news={safeNews} lang={lang} />
    </div>
  );
}
