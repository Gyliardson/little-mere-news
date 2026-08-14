import type { Metadata } from "next";
import { supabase } from "@/lib/supabase/client";
import { safeHttpUrl } from "@/lib/http-url";
import { notFound } from "next/navigation";
import Link from "next/link";

export const revalidate = 3600;

async function getNews(id: string) {
  return supabase.from("news").select("*").eq("id", id).maybeSingle();
}

export async function generateMetadata({ params }: { params: Promise<{ lang: string; id: string }> }): Promise<Metadata> {
  const { lang, id } = await params;
  const isPt = lang === "pt";
  const { data: news, error } = await getNews(id);

  if (error) {
    return {
      title: isPt ? "Artigo temporariamente indisponível" : "Article temporarily unavailable",
      robots: { index: false, follow: false },
    };
  }

  if (!news) return {};

  const title = isPt ? news.title_pt : news.title_en;
  const description = isPt ? news.summary_pt : news.summary_en;
  const canonical = `/${lang}/news/${id}`;

  return {
    title,
    description,
    alternates: {
      canonical,
      languages: { en: `/en/news/${id}`, pt: `/pt/news/${id}` },
    },
    openGraph: {
      type: "article",
      title,
      description,
      url: canonical,
      publishedTime: news.published_at,
      locale: isPt ? "pt_BR" : "en_US",
      alternateLocale: isPt ? ["en_US"] : ["pt_BR"],
    },
    twitter: { card: "summary", title, description },
  };
}

export default async function NewsDetail({ params }: { params: Promise<{ lang: string; id: string }> }) {
  const { lang, id } = await params;
  const isPt = lang === "pt";
  const { data: news, error } = await getNews(id);

  if (error) {
    // Provider details may contain implementation/internal information. The nested
    // route error boundary presents a generic retryable state instead of converting
    // infrastructure failure into a misleading content 404.
    throw new Error("Article data provider unavailable");
  }

  if (!news) notFound();

  const safeSourceUrl = safeHttpUrl(news.source_url);

  return (
    <article className="max-w-3xl mx-auto py-8">
      <Link href={`/${lang}`} className="text-sm font-medium text-primary hover:text-accent transition-colors mb-8 inline-block">
        ← {isPt ? "Voltar para Início" : "Back to Home"}
      </Link>
      <header className="mb-10">
        <div className="flex items-center gap-4 mb-4">
          <span className="px-3 py-1 text-xs font-bold uppercase tracking-wider text-background bg-accent rounded-full">{news.category}</span>
          <time dateTime={news.published_at} className="text-sm text-foreground-muted">
            {new Intl.DateTimeFormat(isPt ? "pt-BR" : "en-US", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(news.published_at))}
          </time>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-6 leading-tight">{isPt ? news.title_pt : news.title_en}</h1>
        <div className="flex items-center justify-between border-y border-primary/20 py-4">
          <span className="text-sm font-medium text-foreground-muted">{isPt ? "Fonte:" : "Source:"} <strong className="text-foreground">{news.source_name}</strong></span>
        </div>
      </header>
      <div className="prose prose-invert prose-lg max-w-none mb-12">
        <p className="text-xl leading-relaxed text-foreground-muted">{isPt ? news.summary_pt : news.summary_en}</p>
      </div>
      <div className="bg-background-secondary border border-primary/20 p-8 rounded-2xl text-center">
        <h2 className="text-2xl font-bold mb-4">{isPt ? "Interessado nesta notícia?" : "Interested in this news?"}</h2>
        <p className="text-foreground-muted mb-6">{isPt ? "Leia o artigo completo diretamente na fonte original para todos os detalhes." : "Read the full article directly from the original source for all the details."}</p>
        {safeSourceUrl ? (
          <a href={safeSourceUrl} target="_blank" rel="noopener noreferrer" className="inline-block px-8 py-4 bg-primary hover:bg-accent text-background font-bold rounded-full transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,255,0.3)] transform hover:-translate-y-1">
            {isPt ? "Ler Artigo Original ↗" : "Read Full Article ↗"}
          </a>
        ) : (
          <p className="text-sm text-foreground-muted" role="status">{isPt ? "Link da fonte indisponível." : "Source link unavailable."}</p>
        )}
      </div>
    </article>
  );
}
