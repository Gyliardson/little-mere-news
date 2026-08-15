"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

export default function ArticleError({ reset }: { reset: () => void }) {
  const params = useParams();
  const isPt = params?.lang === "pt";
  const homeHref = isPt ? "/pt" : "/en";

  return (
    <section
      className="max-w-3xl mx-auto py-16 px-4 text-center"
      role="alert"
      aria-labelledby="article-provider-error-title"
    >
      <div className="bg-background-secondary border border-primary/20 rounded-2xl p-8 md:p-12">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent mb-4">
          {isPt ? "Serviço temporariamente indisponível" : "Service temporarily unavailable"}
        </p>
        <h1 id="article-provider-error-title" className="text-3xl md:text-4xl font-bold mb-4">
          {isPt ? "Artigo temporariamente indisponível" : "Article temporarily unavailable"}
        </h1>
        <p className="text-foreground-muted mb-8 max-w-xl mx-auto">
          {isPt
            ? "Não foi possível carregar este artigo agora. Isso não significa que ele foi removido. Tente novamente em instantes."
            : "This article could not be loaded right now. That does not mean it was removed. Please try again shortly."}
        </p>
        <div className="flex flex-col sm:flex-row justify-center gap-3">
          <button
            type="button"
            onClick={() => reset()}
            className="px-6 py-3 bg-primary hover:bg-accent text-background font-bold rounded-full transition-colors"
          >
            {isPt ? "Tentar novamente" : "Try again"}
          </button>
          <Link
            href={homeHref}
            className="px-6 py-3 border border-primary/30 hover:border-accent text-foreground font-medium rounded-full transition-colors"
          >
            {isPt ? "Voltar para início" : "Back to home"}
          </Link>
        </div>
      </div>
    </section>
  );
}
