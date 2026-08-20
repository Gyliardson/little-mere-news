export default async function PrivacyPolicy({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const isPt = lang === 'pt';

  return (
    <article className="max-w-4xl mx-auto py-12 px-4 prose prose-invert prose-lg">
      <h1 className="text-4xl font-bold tracking-tight mb-8 text-foreground">
        {isPt ? "Política de Privacidade" : "Privacy Policy"}
      </h1>
      <p className="text-foreground-muted mb-6">
        {isPt ? "Última atualização: Agosto de 2026" : "Last updated: August 2026"}
      </p>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "1. Autenticação Administrativa" : "1. Administrative Authentication"}</h2>
        <p className="text-foreground-muted">
          {isPt
            ? "Quando um administrador autorizado faz login, a aplicação usa o Supabase Auth para autenticar a conta e manter o estado da sessão administrativa."
            : "When an authorized administrator signs in, the application uses Supabase Auth to authenticate the account and maintain administrative session state."}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "2. Cookies de Sessão" : "2. Session Cookies"}</h2>
        <p className="text-foreground-muted">
          {isPt
            ? "O fluxo SSR atual usa cookies para manter o estado de autenticação e sessão. O código versionado não implementa Google Analytics, Google AdSense nem cookies de publicidade."
            : "The current SSR flow uses cookies to maintain authentication and session state. The versioned application does not implement Google Analytics, Google AdSense, or advertising cookies."}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "3. Escopo desta Política" : "3. Scope of This Policy"}</h2>
        <p className="text-foreground-muted">
          {isPt
            ? "Esta política descreve somente os comportamentos de privacidade sustentados pelo software versionado neste repositório e não presume mecanismos adicionais de tracking, analytics ou publicidade."
            : "This policy describes only privacy behavior supported by the software versioned in this repository and does not assume additional tracking, analytics, or advertising mechanisms."}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "4. Contato" : "4. Contact"}</h2>
        <p className="text-foreground-muted">
          {isPt
            ? "Para dúvidas sobre esta política, visite nossa página de Contato."
            : "For questions about this policy, please visit our Contact page."}
        </p>
      </section>
    </article>
  );
}
