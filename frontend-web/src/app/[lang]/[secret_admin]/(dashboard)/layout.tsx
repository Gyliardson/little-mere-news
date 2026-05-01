import { redirect } from "next/navigation";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export default async function DashboardAuthLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string; secret_admin: string }>;
}) {
  const { lang, secret_admin } = await params;

  // Auth Guard: verify session server-side
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${lang}/${secret_admin}/login`);
  }

  return <>{children}</>;
}
