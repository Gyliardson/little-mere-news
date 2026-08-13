import type { MetadataRoute } from "next";

const siteUrl = new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000");

export default function robots(): MetadataRoute.Robots {
  const secret = process.env.ADMIN_PHANTOM_PATH?.trim();
  const disallow = ["/api/"];

  if (secret) {
    disallow.push(`/en/${secret}/`, `/pt/${secret}/`);
  }

  return {
    rules: { userAgent: "*", allow: "/", disallow },
    sitemap: new URL("/sitemap.xml", siteUrl).toString(),
  };
}
