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
        {isPt ? "Última atualização: Maio de 2026" : "Last updated: May 2026"}
      </p>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "1. Informações que Coletamos" : "1. Information We Collect"}</h2>
        <p className="text-foreground-muted">
          {isPt 
            ? "Coletamos informações básicas de uso do site (como páginas visitadas e tempo de sessão) através de ferramentas de analytics padronizadas para melhorar nossa plataforma e exibir anúncios relevantes."
            : "We collect basic website usage information (such as visited pages and session time) through standard analytics tools to improve our platform and display relevant ads."}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "2. Google AdSense e Cookies" : "2. Google AdSense and Cookies"}</h2>
        <p className="text-foreground-muted">
          {isPt 
            ? "Fornecedores de terceiros, incluindo o Google, usam cookies para veicular anúncios com base em visitas anteriores do usuário ao seu website ou a outros websites. O uso de cookies de publicidade permite que o Google e seus parceiros veiculem anúncios aos usuários com base nas visitas feitas aos seus sites e/ou a outros sites na Internet."
            : "Third party vendors, including Google, use cookies to serve ads based on a user's prior visits to your website or other websites. Google's use of advertising cookies enables it and its partners to serve ads to your users based on their visit to your sites and/or other sites on the Internet."}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "3. Contato" : "3. Contact"}</h2>
        <p className="text-foreground-muted">
          {isPt 
            ? "Para quaisquer dúvidas sobre esta política, visite nossa página de Contato."
            : "For any questions regarding this policy, please visit our Contact page."}
        </p>
      </section>
    </article>
  );
}
