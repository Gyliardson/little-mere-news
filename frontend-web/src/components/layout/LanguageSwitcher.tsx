"use client";

import { usePathname, useRouter } from "next/navigation";

export default function LanguageSwitcher() {
  const pathname = usePathname();
  const router = useRouter();

  // Se estivermos em /pt/alguma-coisa, isPt é true.
  const isPt = pathname.startsWith("/pt");

  const toggleLanguage = () => {
    // Substitui a base /pt por /en ou vice-versa
    const newPath = isPt 
      ? pathname.replace(/^\/pt/, "/en") 
      : pathname.replace(/^\/en/, "/pt");
    
    // Fallback caso a rota seja a raiz
    if (newPath === pathname && newPath === "/") {
      window.location.href = "/pt";
      return;
    }

    window.location.href = newPath || "/";
  };

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-primary/30 hover:border-accent hover:bg-accent/10 transition-colors text-sm font-bold uppercase tracking-wider"
      aria-label="Toggle Language"
    >
      <span className={!isPt ? "text-accent" : "text-foreground-muted"}>EN</span>
      <span className="text-foreground-muted/50">|</span>
      <span className={isPt ? "text-accent" : "text-foreground-muted"}>PT-BR</span>
    </button>
  );
}
