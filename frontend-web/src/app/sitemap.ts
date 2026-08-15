import type { MetadataRoute } from "next";
import { supabase } from "@/lib/supabase/client";

export const dynamic = "force-dynamic";

const siteUrl = new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000");
const locales = ["en", "pt"] as const;
const staticPages = ["", "/privacy", "/terms", "/contact"] as const;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [];

  for (const lang of locales) {
    for (const path of staticPages) {
      entries.push({
        url: new URL(`/${lang}${path}`, siteUrl).toString(),
        changeFrequency: path === "" ? "hourly" : "monthly",
        priority: path === "" ? 1 : 0.4,
      });
    }
  }

  const { data: news, error } = await supabase.from("news").select("id,published_at");
  if (!error && news) {
    for (const item of news) {
      for (const lang of locales) {
        entries.push({
          url: new URL(`/${lang}/news/${item.id}`, siteUrl).toString(),
          lastModified: item.published_at ? new Date(item.published_at) : undefined,
          changeFrequency: "weekly",
          priority: 0.7,
        });
      }
    }
  }

  return entries;
}
