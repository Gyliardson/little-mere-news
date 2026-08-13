import http from "node:http";

const port = Number(process.env.FAKE_SUPABASE_PORT ?? 54321);
const origin = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const adminId = "11111111-1111-4111-8111-111111111111";

function base64url(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

const now = Math.floor(Date.now() / 1000);
const accessToken = `${base64url({ alg: "HS256", typ: "JWT" })}.${base64url({
  aud: "authenticated",
  exp: now + 3600,
  iat: now,
  sub: adminId,
  email: "admin@example.test",
  role: "authenticated",
  aal: "aal1",
  session_id: "22222222-2222-4222-8222-222222222222",
})}.dGVzdC1zaWduYXR1cmU`;

const user = {
  id: adminId,
  aud: "authenticated",
  role: "authenticated",
  email: "admin@example.test",
  email_confirmed_at: new Date(now * 1000).toISOString(),
  phone: "",
  confirmed_at: new Date(now * 1000).toISOString(),
  last_sign_in_at: new Date(now * 1000).toISOString(),
  app_metadata: { provider: "email", providers: ["email"] },
  user_metadata: {},
  identities: [],
  created_at: new Date(now * 1000).toISOString(),
  updated_at: new Date(now * 1000).toISOString(),
  is_anonymous: false,
};

const news = [
  {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    category: "AI",
    source_name: "Fixture Wire",
    source_url: "https://example.test/articles/fixture-ai",
    title_en: "Deterministic AI fixture",
    summary_en: "Synthetic browser-test content.",
    title_pt: "Fixture determinística de IA",
    summary_pt: "Conteúdo sintético de teste browser.",
    published_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  },
  {
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    category: "Development",
    source_name: "Fixture Wire",
    source_url: "https://example.test/articles/fixture-dev",
    title_en: "Deterministic development fixture",
    summary_en: "Synthetic browser-test content.",
    title_pt: "Fixture determinística de desenvolvimento",
    summary_pt: "Conteúdo sintético de teste browser.",
    published_at: new Date(Date.now() - 86400000).toISOString(),
    created_at: new Date().toISOString(),
  },
];

function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", origin);
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Headers", "authorization, apikey, content-type, x-client-info, x-supabase-api-version, prefer, accept-profile, content-profile");
  res.setHeader("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS");
  res.setHeader("Vary", "Origin");
}

function json(res, status, body, headers = {}) {
  cors(res);
  res.writeHead(status, { "content-type": "application/json", ...headers });
  res.end(JSON.stringify(body));
}

async function readJson(req) {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return raw ? JSON.parse(raw) : {};
}

const server = http.createServer(async (req, res) => {
  cors(res);
  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = new URL(req.url, `http://127.0.0.1:${port}`);

  if (req.method === "POST" && url.pathname === "/auth/v1/token") {
    const body = await readJson(req);
    if (body.email !== "admin@example.test" || body.password !== "admin-password") {
      json(res, 400, { error: "invalid_grant", error_description: "Invalid login credentials" });
      return;
    }
    json(res, 200, {
      access_token: accessToken,
      token_type: "bearer",
      expires_in: 3600,
      expires_at: now + 3600,
      refresh_token: "fixture-refresh-token",
      user,
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/auth/v1/user") {
    if (req.headers.authorization !== `Bearer ${accessToken}`) {
      json(res, 401, { message: "invalid token" });
      return;
    }
    json(res, 200, user);
    return;
  }

  if ((req.method === "GET" || req.method === "HEAD") && url.pathname === "/rest/v1/admin_users") {
    if (req.headers.authorization !== `Bearer ${accessToken}`) {
      json(res, 401, { message: "not authorized" });
      return;
    }
    const wantsObject = String(req.headers.accept ?? "").includes("application/vnd.pgrst.object+json");
    json(res, 200, wantsObject ? { user_id: adminId } : [{ user_id: adminId }]);
    return;
  }

  if ((req.method === "GET" || req.method === "HEAD") && url.pathname === "/rest/v1/news") {
    const headers = { "content-range": `0-${news.length - 1}/${news.length}` };
    if (req.method === "HEAD") {
      cors(res);
      res.writeHead(200, headers);
      res.end();
      return;
    }
    json(res, 200, news, headers);
    return;
  }

  json(res, 404, { message: "fixture endpoint not found" });
});

server.listen(port, "127.0.0.1", () => {
  console.log(`fake Supabase fixture listening on ${port}`);
});

for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
