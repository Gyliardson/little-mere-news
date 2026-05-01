import { supabase } from "@/lib/supabase/client";
import Link from "next/link";

export const revalidate = 3600; // Revalidate at most every hour

export default async function Home({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const isPt = lang === 'pt';

  // Fetch news from Supabase
  const { data: news, error } = await supabase
    .from('news')
    .select('*')
    .order('published_at', { ascending: false })
    .limit(20);

  if (error) {
    console.error("Error fetching news:", error);
  }

  return (
    <article className="space-y-8">
      <header className="mb-8">
        <h2 className="text-3xl font-bold tracking-tight mb-2 text-foreground">
          {isPt ? "Últimas Notícias" : "Latest News"}
        </h2>
        <p className="text-foreground-muted">
          {isPt 
            ? "Fique por dentro das novidades do mundo da tecnologia, IA e desenvolvimento."
            : "Stay updated with the latest in tech, AI, and development."}
        </p>
      </header>

      {news && news.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {news.map((item) => (
            <div 
              key={item.id} 
              className="group relative flex flex-col justify-between p-6 rounded-2xl bg-background-secondary border border-primary/10 hover:border-accent/50 transition-all duration-300 hover:shadow-[0_0_15px_rgba(0,255,255,0.1)] overflow-hidden"
            >
              {/* Category Badge */}
              <div className="absolute top-4 right-4 z-10">
                <span className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-background bg-accent rounded-full">
                  {item.category}
                </span>
              </div>

              <div>
                <time dateTime={item.published_at} className="text-xs text-foreground-muted mb-2 block">
                  {new Intl.DateTimeFormat(isPt ? 'pt-BR' : 'en-US', {
                    day: '2-digit', month: 'short', year: 'numeric'
                  }).format(new Date(item.published_at))}
                </time>
                <h3 className="text-lg font-bold mb-3 group-hover:text-accent transition-colors line-clamp-2">
                  {isPt ? item.title_pt : item.title_en}
                </h3>
                <p className="text-sm text-foreground-muted line-clamp-3">
                  {isPt ? item.summary_pt : item.summary_en}
                </p>
              </div>

              <div className="mt-6 flex items-center justify-between border-t border-primary/10 pt-4">
                <span className="text-xs font-medium text-primary">
                  {item.source_name}
                </span>
                <Link 
                  href={`/${lang}/news/${item.id}`}
                  className="text-xs font-bold text-accent hover:text-accent-secondary transition-colors"
                  aria-label={isPt ? `Ler mais sobre ${item.title_pt}` : `Read more about ${item.title_en}`}
                >
                  {isPt ? "Ler Notícia ↗" : "Read News ↗"}
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-12 text-center text-foreground-muted border border-dashed border-primary/20 rounded-2xl">
          <p>{isPt ? "Nenhuma notícia encontrada hoje." : "No news found today."}</p>
        </div>
      )}
    </article>
  );
}
