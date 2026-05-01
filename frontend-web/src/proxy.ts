import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const locales = ['en', 'pt']
const defaultLocale = 'en'

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Check if there is any supported locale in the pathname
  const pathnameHasLocale = locales.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
  )

  if (pathnameHasLocale) return

  // Redirect if there is no locale
  request.nextUrl.pathname = `/${defaultLocale}${pathname}`
  
  // e.g. incoming request is /
  // The new URL is now /en/
  return NextResponse.redirect(request.nextUrl)
}

export const config = {
  matcher: [
    // Skip all internal paths (_next) and public folder files
    '/((?!_next|logo.png|favicon.ico).*)',
  ],
}
