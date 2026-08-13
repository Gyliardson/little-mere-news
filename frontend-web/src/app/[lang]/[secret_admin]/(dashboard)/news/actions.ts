"use server";

import { getAdminContext } from "@/lib/auth/admin";
import { revalidatePath } from "next/cache";

async function getMutationContext() {
  const context = await getAdminContext();
  if (!context.user) return { ...context, accessError: "Unauthorized" } as const;
  if (!context.isAdmin) return { ...context, accessError: "Forbidden" } as const;
  return { ...context, accessError: null } as const;
}

export async function updateNews(
  id: string,
  data: {
    title_en?: string;
    title_pt?: string;
    summary_en?: string;
    summary_pt?: string;
    category?: string;
  }
) {
  const { supabase, accessError } = await getMutationContext();
  if (accessError) return { error: accessError };

  const { error } = await supabase.from("news").update(data).eq("id", id);
  if (error) return { error: error.message };

  revalidatePath("/", "layout");
  return { success: true };
}

export async function deleteNews(id: string) {
  const { supabase, accessError } = await getMutationContext();
  if (accessError) return { error: accessError };

  const { error } = await supabase.from("news").delete().eq("id", id);
  if (error) return { error: error.message };

  revalidatePath("/", "layout");
  return { success: true };
}
