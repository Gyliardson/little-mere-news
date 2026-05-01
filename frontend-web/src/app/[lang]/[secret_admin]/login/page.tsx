"use client";

import { Lock, Loader2, AlertCircle } from "lucide-react";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";

const t = {
  pt: {
    title: "Acesso Restrito",
    subtitle: "Autenticação via Supabase Auth. Apenas administradores autorizados.",
    emailLabel: "Email Corporativo",
    passwordLabel: "Senha",
    submit: "Autenticar",
    loading: "Verificando...",
    errorInvalid: "Email ou senha inválidos. Tente novamente.",
    errorGeneric: "Erro ao conectar. Tente novamente em instantes.",
  },
  en: {
    title: "Restricted Access",
    subtitle: "Authentication via Supabase Auth. Authorized administrators only.",
    emailLabel: "Corporate Email",
    passwordLabel: "Password",
    submit: "Authenticate",
    loading: "Verifying...",
    errorInvalid: "Invalid email or password. Please try again.",
    errorGeneric: "Connection error. Please try again shortly.",
  },
};

export default function AdminLogin() {
  const params = useParams();
  const router = useRouter();
  const lang = (params.lang as string) || "en";
  const secret_admin = params.secret_admin as string;
  const isPt = lang === "pt";
  const labels = isPt ? t.pt : t.en;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const supabase = createBrowserSupabaseClient();
      const { error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (authError) {
        setError(labels.errorInvalid);
        setLoading(false);
        return;
      }

      // Successful login - redirect to dashboard
      router.push(`/${lang}/${secret_admin}`);
      router.refresh();
    } catch {
      setError(labels.errorGeneric);
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center min-h-[80vh] p-4 absolute inset-0 bg-background z-50">
      <div className="w-full max-w-md p-8 bg-background-secondary border border-primary/20 rounded-2xl shadow-2xl relative">
        <div className="flex justify-center mb-6">
          <div className="p-4 bg-background rounded-full border border-primary/30 shadow-[0_0_15px_rgba(0,128,128,0.2)]">
            <Lock className="w-8 h-8 text-primary" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-center mb-2 text-foreground">
          {labels.title}
        </h1>
        <p className="text-sm text-foreground-muted text-center mb-8">
          {labels.subtitle}
        </p>

        {error && (
          <div className="flex items-center gap-2 p-3 mb-6 bg-red-400/10 border border-red-400/30 rounded-xl text-red-400 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground-muted mb-1" htmlFor="email">
              {labels.emailLabel}
            </label>
            <input 
              type="email" 
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
              className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
              placeholder="admin@littlemere.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground-muted mb-1" htmlFor="password">
              {labels.passwordLabel}
            </label>
            <input 
              type="password" 
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
              placeholder="••••••••"
            />
          </div>
          <button 
            type="submit"
            disabled={loading}
            className="w-full py-3 mt-4 bg-primary hover:bg-accent text-background font-bold rounded-xl transition-all duration-300 shadow-[0_0_15px_rgba(0,255,255,0.1)] hover:shadow-[0_0_20px_rgba(0,255,255,0.3)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {labels.loading}
              </>
            ) : (
              labels.submit
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
