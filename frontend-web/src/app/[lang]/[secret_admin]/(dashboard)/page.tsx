import { createServerSupabaseClient } from "@/lib/supabase/server";
import DashboardCharts from "@/components/admin/DashboardCharts";
import { Newspaper, CalendarDays, Radio } from "lucide-react";

export const revalidate = 60; // Cache for 1 minute to improve performance

const t = {
  pt: {
    title: "Visão Geral",
    subtitle: "Métricas de processamento local das VMs (Harvester e Brain).",
    totalWeek: "Total Processado (Semana)",
    articlesToday: "Artigos Hoje",
    activeSources: "Fontes Ativas",
  },
  en: {
    title: "Overview",
    subtitle: "Local VM processing metrics (Harvester & Brain).",
    totalWeek: "Total Processed (Week)",
    articlesToday: "Articles Today",
    activeSources: "Active Sources",
  },
};

export default async function DashboardOverview({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const isPt = lang === "pt";
  const labels = isPt ? t.pt : t.en;

  const supabase = await createServerSupabaseClient();

  // Calculate date boundaries
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();

  // Execute all queries in parallel for maximum performance
  const [
    { count: weekTotal },
    { count: todayTotal },
    { data: sourcesData },
    { data: weekData },
    { data: categoryDataRaw }
  ] = await Promise.all([
    // Query 1: Total processed this week
    supabase
      .from("news")
      .select("*", { count: "exact", head: true })
      .gte("published_at", weekAgo),

    // Query 2: Articles today
    supabase
      .from("news")
      .select("*", { count: "exact", head: true })
      .gte("published_at", todayStart),

    // Query 3: Distinct active sources
    supabase
      .from("news")
      .select("source_name"),

    // Query 4: Daily volume for the last 7 days (for bar chart)
    supabase
      .from("news")
      .select("published_at")
      .gte("published_at", weekAgo)
      .order("published_at", { ascending: true }),

    // Query 5: Category distribution (for pie chart)
    supabase
      .from("news")
      .select("category")
  ]);

  // Process data for charts/metrics
  const uniqueSources = new Set(sourcesData?.map((s) => s.source_name)).size;

  const dayNames = isPt
    ? ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]
    : ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  // Group by day of week
  const dailyCounts: Record<string, number> = {};
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
    const key = d.toISOString().split("T")[0];
    dailyCounts[key] = 0;
  }

  weekData?.forEach((item) => {
    const key = new Date(item.published_at).toISOString().split("T")[0];
    if (dailyCounts[key] !== undefined) {
      dailyCounts[key]++;
    }
  });

  const dailyData = Object.entries(dailyCounts).map(([dateStr, count]) => {
    const d = new Date(dateStr);
    return { name: dayNames[d.getDay()], count };
  });

  // Group by category
  const categoryCounts: Record<string, number> = {};
  categoryDataRaw?.forEach((item) => {
    const cat = item.category || "Other";
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
  });

  const categoryData = Object.entries(categoryCounts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  return (
    <div className="space-y-8 pb-12">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          {labels.title}
        </h1>
        <p className="text-foreground-muted">{labels.subtitle}</p>
      </header>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 bg-background-secondary border border-primary/20 rounded-2xl flex items-start gap-4">
          <div className="p-3 bg-accent/10 rounded-xl">
            <Newspaper className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-foreground-muted mb-1">
              {labels.totalWeek}
            </h3>
            <p className="text-3xl font-bold text-accent">
              {(weekTotal ?? 0).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="p-6 bg-background-secondary border border-primary/20 rounded-2xl flex items-start gap-4">
          <div className="p-3 bg-primary/10 rounded-xl">
            <CalendarDays className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-foreground-muted mb-1">
              {labels.articlesToday}
            </h3>
            <p className="text-3xl font-bold text-primary">
              {todayTotal ?? 0}
            </p>
          </div>
        </div>

        <div className="p-6 bg-background-secondary border border-primary/20 rounded-2xl flex items-start gap-4">
          <div className="p-3 bg-accent-secondary/10 rounded-xl">
            <Radio className="w-6 h-6 text-accent-secondary" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-foreground-muted mb-1">
              {labels.activeSources}
            </h3>
            <p className="text-3xl font-bold text-accent-secondary">
              {uniqueSources}
            </p>
          </div>
        </div>
      </div>

      {/* Charts */}
      <DashboardCharts
        lang={lang}
        dailyData={dailyData}
        categoryData={categoryData}
      />
    </div>
  );
}
