import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function getAdminContext() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return { supabase, user: null, isAdmin: false } as const;
  }

  const { data: membership, error: membershipError } = await supabase
    .from("admin_users")
    .select("user_id")
    .eq("user_id", user.id)
    .maybeSingle();

  return {
    supabase,
    user,
    isAdmin: !membershipError && membership?.user_id === user.id,
  } as const;
}
