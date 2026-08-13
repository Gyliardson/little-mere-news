import { redirect } from "next/navigation";
import { getAdminContext } from "@/lib/auth/admin";

export default async function DashboardAuthLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string; secret_admin: string }>;
}) {
  const { lang, secret_admin } = await params;
  const { user, isAdmin } = await getAdminContext();

  if (!user) {
    redirect(`/${lang}/${secret_admin}/login`);
  }

  if (!isAdmin) {
    redirect(`/${lang}/${secret_admin}/login?error=forbidden`);
  }

  return <>{children}</>;
}
