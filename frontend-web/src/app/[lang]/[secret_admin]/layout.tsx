import { notFound } from "next/navigation";
import AdminSidebar from "@/components/admin/AdminSidebar";

export default async function AdminLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string; secret_admin: string }>;
}) {
  const { secret_admin, lang } = await params;

  // Phantom Route Guard
  if (secret_admin !== process.env.ADMIN_PHANTOM_PATH) {
    notFound();
  }

  return (
    <div className="fixed inset-0 z-[60] flex bg-background">
      <AdminSidebar lang={lang} secret_admin={secret_admin} />
      <div className="flex-1 overflow-y-auto p-6 md:p-8">
        {children}
      </div>
    </div>
  );
}
