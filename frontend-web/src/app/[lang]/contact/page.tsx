import { Mail, Code, Briefcase, Globe } from "lucide-react";

export default async function Contact({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const isPt = lang === 'pt';

  return (
    <article className="max-w-3xl mx-auto py-12 px-4">
      <header className="mb-12 text-center">
        <h1 className="text-4xl font-bold tracking-tight mb-4 text-foreground">
          {isPt ? "Entre em Contato" : "Get in Touch"}
        </h1>
        <p className="text-foreground-muted text-lg">
          {isPt 
            ? "Conecte-se comigo pelas redes profissionais abaixo ou envie um email."
            : "Connect with me through the professional networks below or send an email."}
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Email */}
        <a 
          href="mailto:gyliardson@outlook.com"
          className="flex flex-col items-center justify-center p-8 bg-background-secondary border border-primary/20 rounded-2xl hover:border-accent hover:bg-accent/5 transition-all duration-300 group"
        >
          <div className="w-16 h-16 rounded-full bg-background flex items-center justify-center mb-4 group-hover:scale-110 transition-transform shadow-[0_0_15px_rgba(0,128,128,0.2)]">
            <Mail className="w-8 h-8 text-primary group-hover:text-accent transition-colors" />
          </div>
          <h2 className="text-xl font-bold text-foreground mb-1">Email</h2>
          <span className="text-sm text-foreground-muted group-hover:text-accent transition-colors">
            gyliardson@outlook.com
          </span>
        </a>

        {/* LinkedIn */}
        <a 
          href="https://linkedin.com/in/gyliardson-keitison"
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col items-center justify-center p-8 bg-background-secondary border border-primary/20 rounded-2xl hover:border-accent hover:bg-accent/5 transition-all duration-300 group"
        >
          <div className="w-16 h-16 rounded-full bg-background flex items-center justify-center mb-4 group-hover:scale-110 transition-transform shadow-[0_0_15px_rgba(0,128,128,0.2)]">
            <Briefcase className="w-8 h-8 text-primary group-hover:text-accent transition-colors" />
          </div>
          <h2 className="text-xl font-bold text-foreground mb-1">LinkedIn</h2>
          <span className="text-sm text-foreground-muted group-hover:text-accent transition-colors">
            in/gyliardson-keitison
          </span>
        </a>

        {/* GitHub */}
        <a 
          href="https://github.com/Gyliardson"
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col items-center justify-center p-8 bg-background-secondary border border-primary/20 rounded-2xl hover:border-accent hover:bg-accent/5 transition-all duration-300 group"
        >
          <div className="w-16 h-16 rounded-full bg-background flex items-center justify-center mb-4 group-hover:scale-110 transition-transform shadow-[0_0_15px_rgba(0,128,128,0.2)]">
            <Code className="w-8 h-8 text-primary group-hover:text-accent transition-colors" />
          </div>
          <h2 className="text-xl font-bold text-foreground mb-1">GitHub</h2>
          <span className="text-sm text-foreground-muted group-hover:text-accent transition-colors">
            github.com/Gyliardson
          </span>
        </a>

        {/* Portfolio */}
        <a 
          href="https://gyliardson.github.io/gyliardson/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col items-center justify-center p-8 bg-background-secondary border border-primary/20 rounded-2xl hover:border-accent hover:bg-accent/5 transition-all duration-300 group"
        >
          <div className="w-16 h-16 rounded-full bg-background flex items-center justify-center mb-4 group-hover:scale-110 transition-transform shadow-[0_0_15px_rgba(0,128,128,0.2)]">
            <Globe className="w-8 h-8 text-primary group-hover:text-accent transition-colors" />
          </div>
          <h2 className="text-xl font-bold text-foreground mb-1">Portfolio</h2>
          <span className="text-sm text-foreground-muted group-hover:text-accent transition-colors">
            {isPt ? "Acesse meu Portfólio" : "Visit my Portfolio"}
          </span>
        </a>
      </div>
    </article>
  );
}
