export default async function TermsOfService({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const isPt = lang === 'pt';

  return (
    <article className="max-w-4xl mx-auto py-12 px-4 prose prose-invert prose-lg">
      <h1 className="text-4xl font-bold tracking-tight mb-8 text-foreground">
        {isPt ? "Termos de Serviço" : "Terms of Service"}
      </h1>
      <p className="text-foreground-muted mb-6">
        {isPt ? "Última atualização: Maio de 2026" : "Last updated: May 2026"}
      </p>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "1. Aceitação dos Termos" : "1. Acceptance of Terms"}</h2>
        <p className="text-foreground-muted">
          {isPt 
            ? "Ao acessar o portal Little Mere News, você concorda em cumprir estes termos de serviço, todas as leis e regulamentos aplicáveis, e concorda que é responsável pelo cumprimento de todas as leis locais aplicáveis."
            : "By accessing the Little Mere News portal, you agree to be bound by these terms of service, all applicable laws and regulations, and agree that you are responsible for compliance with any applicable local laws."}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "2. Uso de Conteúdo" : "2. Use of Content"}</h2>
        <p className="text-foreground-muted">
          {isPt 
            ? "Os resumos de notícias fornecidos neste site são gerados automaticamente e servem apenas para fins informativos. Sempre providenciamos links para as fontes originais, onde os artigos completos e direitos autorais pertencem aos seus respectivos autores e publicadores."
            : "The news summaries provided on this site are automatically generated and serve for informational purposes only. We always provide links to the original sources, where full articles and copyrights belong to their respective authors and publishers."}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-foreground">{isPt ? "3. Isenção de Responsabilidade" : "3. Disclaimer"}</h2>
        <p className="text-foreground-muted">
          {isPt 
            ? "Os materiais no site da Little Mere News são fornecidos 'como estão'. Não oferecemos garantias, expressas ou implícitas, e, por este meio, isentamos e negamos todas as outras garantias, incluindo, sem limitação, garantias implícitas ou condições de comercialização."
            : "The materials on Little Mere News's website are provided on an 'as is' basis. We make no warranties, expressed or implied, and hereby disclaims and negates all other warranties including, without limitation, implied warranties or conditions of merchantability."}
        </p>
      </section>
    </article>
  );
}
