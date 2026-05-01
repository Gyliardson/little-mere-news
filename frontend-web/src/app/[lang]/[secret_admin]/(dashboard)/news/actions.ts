"use server";

import { createServerSupabaseClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

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
  const supabase = await createServerSupabaseClient();

  // Verify auth
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return { error: "Unauthorized" };
  }

  const { error } = await supabase
    .from("news")
    .update(data)
    .eq("id", id);

  if (error) {
    return { error: error.message };
  }

  revalidatePath("/", "layout");
  return { success: true };
}

export async function deleteNews(id: string) {
  const supabase = await createServerSupabaseClient();

  // Verify auth
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return { error: "Unauthorized" };
  }

  const { error } = await supabase
    .from("news")
    .delete()
    .eq("id", id);

  if (error) {
    return { error: error.message };
  }

  revalidatePath("/", "layout");
  return { success: true };
}
