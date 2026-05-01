import { createBrowserClient } from '@supabase/ssr'
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

/**
 * Browser client - for use in Client Components ("use client").
 * Handles auth session via cookies automatically.
 */
export function createBrowserSupabaseClient() {
  return createBrowserClient(supabaseUrl, supabaseAnonKey)
}

/**
 * Legacy singleton client - kept for backward compatibility with
 * existing public-facing pages (home, news detail) that don't need auth.
 */
export const supabase = createClient(supabaseUrl, supabaseAnonKey)
