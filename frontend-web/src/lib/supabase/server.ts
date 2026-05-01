import { createServerClient as createSSRServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

/**
 * Server client - for use in Server Components and Server Actions.
 * Reads/writes cookies for session management.
 */
export async function createServerSupabaseClient() {
  const cookieStore = await cookies()

  return createSSRServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          )
        } catch {
          // setAll can fail in Server Components (read-only context).
          // This is expected and safe to ignore - cookies will be set
          // by the middleware or Server Actions instead.
        }
      },
    },
  })
}
