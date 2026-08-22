<div align="center">

# Little Mere News

**Un pipeline determinista de noticias tecnológicas con límites explícitos de IA, colas y autorización.**

Little Mere News combina un portal y CMS en Next.js, ingestión finita de RSS/Atom en Python, un límite configurable de proveedor de IA, colas duraderas de publicación y controles de autorización con Supabase/PostgreSQL.

<a href="../../../README.md">English</a> · <a href="../pt-BR/README.md">Português</a> · <a href="../ja/README.md">日本語</a> · <strong>Español</strong>

[![CI](https://github.com/Gyliardson/little-mere-news/actions/workflows/ci.yml/badge.svg)](https://github.com/Gyliardson/little-mere-news/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](../../../LICENSE)

</div>

## Descripción general

Little Mere News transforma resúmenes de feeds RSS/Atom configurados en payloads bilingües de artículos en inglés/portugués, valida la estructura generada, transfiere el trabajo mediante colas recuperables después de fallos y publica a través de un límite controlado de Supabase/PostgreSQL para el portal público y el CMS administrativo.

El repositorio separa la ingestión de fuentes, la generación asistida por IA, la publicación, la autorización de base de datos y la entrega del frontend para que cada límite pueda revisarse y probarse de forma independiente.

## ¿Por qué Little Mere News?

| Ingestión determinista de feeds | Límite explícito de IA / editorial | Integridad duradera de publicación |
| --- | --- | --- |
| Consultas RSS/Atom acotadas, validación de fuente/vigencia, lotes finitos del Harvester y datos de prueba deterministas mantienen la verificación crítica independiente de feeds reales. | La generación por IA es explícita y configurable; la validación de esquema limita la forma del payload sin afirmar verificación factual. | La identidad inmutable de transferencia, los reintentos/cuarentena acotados y la unicidad de base de datos protegen el trabajo ante fallos abruptos, reintentos y reprocesamiento. |

## Capacidades principales

- portal público de noticias tecnológicas y CMS administrativo con Next.js App Router;
- payloads bilingües inglés/portugués generados a partir de **resúmenes de feeds** RSS/Atom configurados;
- ejecución finita del Harvester con transporte externo acotado y controles de destino orientados a mitigar SSRF;
- límite configurable de proveedor de IA compatible con Ollama para la generación normal de artículos;
- control duradero de la posesión de trabajos del Harvester y de los estados inbox/processing del Publisher;
- reintentos acotados del Publisher, cuarentena duradera, idempotencia por `source_url` segura ante reprocesamiento y upsert;
- Supabase Auth, pertenencia explícita a `public.admin_users`, autorización del lado del servidor y PostgreSQL RLS;
- controles deterministas de frontend, Python, PostgreSQL, navegador, dependencias, detección de secretos y CodeQL.

## Arquitectura

```mermaid
flowchart LR
    Feeds["Feeds RSS / Atom configurados"] --> Harvester["Harvester Python<br/>lote finito y acotado"]
    Harvester --> AI["Proveedor de IA configurable<br/>límite compatible con Ollama"]
    AI --> Validate["Validación de salida estructurada"]
    Validate --> Queue["Transferencia duradera<br/>spool del Publisher"]
    Queue --> Publisher["Publisher Python<br/>reintentos + upsert idempotente"]
    Publisher --> DB[(Supabase / PostgreSQL)]
    DB --> Portal["Portal Next.js SSR"]
    DB --> CMS["CMS administrativo"]
```

El Harvester procesa los datos de feeds configurados en lugar de descargar las páginas completas de los artículos de las fuentes editoras. El estado y la autorización de la base de datos se versionan en `supabase/`, mientras que la topología opcional Hyper-V/Ollama sigue siendo una opción de despliegue y no un requisito arquitectónico.

## Pipeline de contenido

`feeds RSS/Atom configurados → consulta/análisis acotados → validación de vigencia/fuente → normalización del resumen del feed → generación por IA → validación de salida estructurada → transferencia duradera del Harvester → spool/reintentos del Publisher → Supabase/PostgreSQL → frontend`

Cada invocación del Harvester es un **lote finito**. El repositorio no versiona un bucle de sondeo continuo ni un planificador de ingestión. El valor de 24 horas es una ventana de vigencia, `Infrastructure/Run-LMN-Batch.ps1` es un orquestador explícito de lotes y la revalidación del frontend no define la cadencia de ingestión.

## Aspectos técnicos destacados

- **Ingestión basada en el resumen del feed.** La generación normal usa el texto normalizado de `summary` de la entrada RSS/Atom y URLs de fuente duraderas; no obtiene la página completa del artículo de la fuente editora.
- **Límite de IA configurable.** `OLLAMA_API_URL` selecciona el endpoint del proveedor. Ollama local es la convención de despliegue predeterminada documentada, no una garantía arquitectónica de que la inferencia permanezca local.
- **Validación de salida estructurada.** La salida de IA debe satisfacer el contrato esperado de JSON/campos del artículo antes de entrar en la ruta de publicación.
- **Posesión duradera de colas.** Los trabajos del Harvester y los archivos inbox/processing del Publisher usan identidad específica para que la limpieza no elimine trabajo más nuevo en una ruta anteriormente compartida.
- **Reintentos acotados e idempotencia.** Los reintentos del Publisher usan evidencia estructurada de transitoriedad, metadatos duraderos, cuarentena y unicidad de base de datos en `news.source_url`.
- **Auth + pertenencia administrativa + RLS.** Supabase Auth establece identidad, las comprobaciones del lado del servidor exigen `public.admin_users` y PostgreSQL RLS restringe de forma independiente las mutaciones expuestas al navegador.
- **CI determinista.** Las pruebas críticas usan datos de prueba del repositorio y servicios locales/desechables en vez de depender de feeds reales, Supabase de producción, Ollama, GPU o Hyper-V.
- **Límite explícito de planificación.** No se versiona ningún planificador ni bucle continuo de ingestión; el filtro de vigencia no debe describirse como cadencia de ejecución.

## Interfaz

Las capturas representativas propiedad del repositorio se muestran con un ancho legible, en vez de comprimirse en un diseño denso de dos columnas.

### Portal público

<p align="center">
  <img src="../../assets/readme/home.png" width="900" alt="Página principal del portal público de Little Mere News">
</p>

### Panel administrativo

<p align="center">
  <img src="../../assets/readme/dashboard.png" width="900" alt="Panel administrativo de Little Mere News">
</p>

### Inicio de sesión administrativo

<p align="center">
  <img src="../../assets/readme/login.png" width="900" alt="Inicio de sesión administrativo de Little Mere News">
</p>

### Gestión de artículos del CMS

<p align="center">
  <img src="../../assets/readme/cms_list.png" width="900" alt="Lista de artículos del CMS de Little Mere News">
</p>

## Límite de IA / editorial

La generación normal de artículos del Harvester requiere una respuesta válida de IA; no existe una ruta alternativa con contenido bruto ni una ruta sin IA que cree silenciosamente un artículo normal cuando falla el proveedor.

La salida de IA puede contener errores factuales o alucinaciones, omitir contexto o presentar desviaciones durante la paráfrasis, traducción o localización. La validación de salida estructurada verifica la forma del payload, **no la exactitud factual**, y el repositorio no implementa verificación de hechos independiente. Los extractos de feeds también pueden estar incompletos o truncados. El editor/fuente original sigue siendo la referencia autoritativa para el contexto completo y el significado editorial.

Como `OLLAMA_API_URL` es configurable, un despliegue local con Ollama es una convención de la topología documentada, no una garantía de que toda inferencia sea local.

## Inicio rápido

### Frontend

```bash
cd frontend-web
npm ci
cp .env.example .env.local
npm run dev
```

Configura los valores públicos de Supabase y `ADMIN_PHANTOM_PATH` en `.env.local`. Mantén `SUPABASE_SERVICE_ROLE_KEY` solo en el servidor y nunca la expongas mediante `NEXT_PUBLIC_*`, código del navegador, capturas, registros o archivos versionados.

Para el contrato de ejecución del repositorio, configuración de la base de datos, workers Python y verificación en entorno limpio, consulta la [documentación de despliegue](../../operations/DEPLOYMENT.md). Los comandos deterministas de pruebas locales están en [pruebas](../../assurance/TESTING.md).

## Calidad y seguridad

La seguridad **no depende** de una URL administrativa difícil de adivinar. `ADMIN_PHANTOM_PATH` solo oculta la ruta y no constituye autenticación, autorización ni un límite de seguridad.

El acceso administrativo se aplica mediante tres capas distintas:

1. Supabase Auth establece la sesión autenticada.
2. La autorización del lado del servidor comprueba la pertenencia explícita a `public.admin_users`.
3. PostgreSQL RLS restringe de forma independiente las escrituras expuestas al navegador a administradores autenticados.

La CI ejercita calidad de compilación/tipos del frontend, pruebas deterministas de Harvester y Publisher, contratos de migraciones/RLS de PostgreSQL, E2E/accesibilidad en navegador, auditoría de dependencias, detección de secretos versionados y CodeQL. Un control superado es evidencia de la propiedad que ejecuta, no una garantía universal de preparación para producción o seguridad.

Consulta [seguridad de red saliente](../../security/OUTBOUND_NETWORK_SECURITY.md) y [pruebas/garantía](../../assurance/TESTING.md) para los límites detallados.

## Documentación

El [centro de documentación técnica](../../README.md) es el índice canónico para el material de ingeniería detallado.

- [Seguridad — límite de confianza de feeds salientes](../../security/OUTBOUND_NETWORK_SECURITY.md)
- [Fiabilidad — posesión de la cola del Publisher](../../reliability/PUBLISHER_QUEUE_OWNERSHIP.md)
- [Fiabilidad — política de reintentos del Publisher](../../reliability/PUBLISHER_RETRY_POLICY.md)
- [Operaciones — despliegue y contrato de ejecución en entorno limpio](../../operations/DEPLOYMENT.md)
- [Garantía — pruebas deterministas](../../assurance/TESTING.md)

La documentación técnica detallada sigue siendo canónica en inglés; la presentación pública del proyecto se mantiene en cuatro idiomas.

## Limitaciones operativas

- Las fuentes editoras externas y los feeds pueden cambiar metadatos, disponibilidad, redirecciones o comportamiento de límites de solicitudes sin aviso.
- La generación normal del Harvester requiere una respuesta válida de IA; la salida de IA no es una verdad factual autoritativa.
- Las ejecuciones del Harvester son lotes finitos. No se versiona ningún planificador ni bucle continuo de sondeo, y la ventana de vigencia de 24 horas no es una cadencia de ingestión.
- Los datos de prueba deterministas y la CI no sustituyen comprobaciones rápidas específicas del despliegue para Supabase de producción, red, DNS, disponibilidad del proveedor o configuración de plataforma.
- Las migraciones de producción deben revisarse frente a los datos existentes; la migración de unicidad no elimina duplicados de forma silenciosa de manera intencionada.
- La orquestación Hyper-V es opcional y específica del entorno, no la única ruta admitida de desarrollo/ejecución.

## Licencia / límite de contenido de terceros

El repositorio usa la **Licencia MIT** estándar para el software y los materiales originales del proyecto, en la medida aplicable. La licencia MIT **no relicencia** artículos de editores, contenido de feeds RSS/Atom de terceros, logos o marcas de terceros ni material editorial externo.

Los derechos sobre contenido externo siguen sujetos a los términos aplicables de cada fuente y a sus respectivos titulares. Consumir o analizar un feed RSS/Atom **no**, por sí mismo, concede derechos de republicación ni establece permiso para reutilizar contenido del editor.

Consulta [LICENSE](../../../LICENSE) para la licencia del software del repositorio.

## Autor

**Gyliardson Keitison** · [GitHub](https://github.com/Gyliardson) · [LinkedIn](https://www.linkedin.com/in/gyliardson-keitison)
