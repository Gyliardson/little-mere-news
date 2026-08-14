import http from "node:http";

const port = Number(process.env.FAKE_SUPABASE_PORT ?? 54321);
const origin = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const adminId = "11111111-1111-4111-8111-111111111111";
const viewerId = "33333333-3333-4333-8333-333333333333";

function base64url(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

const now = Math.floor(Date.now() / 1000);

function makeToken(id, email, sessionId) {
  return `${base64url({ alg: "HS256", typ: "JWT" })}.${base64url({
    aud: "authenticated",
    exp: now + 3600,
    iat: now,
    sub: id,
    email,
    role: "authenticated",
    aal: "aal1",
    session_id: sessionId,
  })}.dGVzdC1zaWduYXR1cmU`;
}

const adminToken = makeToken(
  adminId,
  "admin@example.test",
  "22222222-2222-4222-8222-222222222222",
);
const viewerToken = makeToken(
  viewerId,
  "viewer@example.test",
  "44444444-4444-4444-8444-444444444444",
);

function makeUser(id, email) {
  const timestamp = new Date(now * 1000).toISOString();
  return {
    id,
    aud: "authenticated",
    role: "authenticated",
    email,
    email_confirmed_at: timestamp,
    phone: "",
    confirmed_at: timestamp,
    last_sign_in_at: timestamp,
    app_metadata: { provider: "email", providers: ["email"] },
    user_metadata: {},
    identities: [],
    created_at: timestamp,
    updated_at: timestamp,
    is_anonymous: false,
  };
}

const adminUser = makeUser(adminId, "admin@example.test");
const viewerUser = makeUser(viewerId, "viewer@example.test");
const sessions = new Map([
  [adminToken, adminUser],
  [viewerToken, viewerUser],
]);

function initialNews() {
  return [
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
}

let news = initialNews();
let failNewsReads = false;
let mutationEvents = [];

function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", origin);
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader(
    "Access-Control-Allow-Headers",
    "authorization, apikey, content-type, x-client-info, x-supabase-api-version, prefer, accept-profile, content-profile",
  );
  res.setHeader("Access-Control-Allow-Methods", "GET, HEAD, POST, PATCH, DELETE, OPTIONS");
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

function bearerToken(req) {
  const value = req.headers.authorization ?? "";
  return value.startsWith("Bearer ") ? value.slice("Bearer ".length) : "";
}

function currentUser(req) {
  return sessions.get(bearerToken(req)) ?? null;
}

function selectedNews(url) {
  const idFilter = url.searchParams.get("id");
  if (!idFilter?.startsWith("eq.")) return news;
  const id = idFilter.slice("eq.".length);
  return news.filter((item) => item.id === id);
}

function wantsObject(req) {
  return String(req.headers.accept ?? "").includes("application/vnd.pgrst.object+json");
}

function requireAdminMutation(req, res) {
  const user = currentUser(req);
  if (!user) {
    json(res, 401, { code: "42501", message: "not authorized" });
    return null;
  }
  if (user.id !== adminId) {
    json(res, 403, { code: "42501", message: "permission denied" });
    return null;
  }
  return user;
}

const server = http.createServer(async (req, res) => {
  cors(res);
  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = new URL(req.url, `http://127.0.0.1:${port}`);

  if (url.pathname === "/__test__/state" && req.method === "GET") {
    json(res, 200, { failNewsReads, mutationEvents, news });
    return;
  }

  if (url.pathname === "/__test__/reset" && req.method === "POST") {
    news = initialNews();
    failNewsReads = false;
    mutationEvents = [];
    json(res, 200, { ok: true });
    return;
  }

  if (url.pathname === "/__test__/news-error" && req.method === "POST") {
    const body = await readJson(req);
    failNewsReads = Boolean(body.enabled);
    json(res, 200, { failNewsReads });
    return;
  }

  if (req.method === "POST" && url.pathname === "/auth/v1/token") {
    const body = await readJson(req);
    let session = null;
    if (body.email === "admin@example.test" && body.password === "admin-password") {
      session = { token: adminToken, user: adminUser };
    } else if (body.email === "viewer@example.test" && body.password === "viewer-password") {
      session = { token: viewerToken, user: viewerUser };
    }

    if (!session) {
      json(res, 400, {
        error: "invalid_grant",
        error_description: "Invalid login credentials",
      });
      return;
    }

    json(res, 200, {
      access_token: session.token,
      token_type: "bearer",
      expires_in: 3600,
      expires_at: now + 3600,
      refresh_token: `fixture-refresh-${session.user.id}`,
      user: session.user,
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/auth/v1/user") {
    const user = currentUser(req);
    if (!user) {
      json(res, 401, { message: "invalid token" });
      return;
    }
    json(res, 200, user);
    return;
  }

  if ((req.method === "GET" || req.method === "HEAD") && url.pathname === "/rest/v1/admin_users") {
    const user = currentUser(req);
    if (!user) {
      json(res, 401, { message: "not authorized" });
      return;
    }

    const membership = user.id === adminId ? { user_id: adminId } : null;
    const objectResponse = wantsObject(req);
    if (objectResponse && !membership) {
      json(res, 406, { code: "PGRST116", message: "No rows found" });
      return;
    }
    json(res, 200, objectResponse ? membership : membership ? [membership] : []);
    return;
  }

  if ((req.method === "GET" || req.method === "HEAD") && url.pathname === "/rest/v1/news") {
    if (failNewsReads) {
      json(res, 503, { code: "E2E_PROVIDER_FAILURE", message: "synthetic provider failure" });
      return;
    }

    const selected = selectedNews(url);
    if (req.method === "HEAD") {
      cors(res);
      res.writeHead(200, { "content-range": `0-${Math.max(selected.length - 1, 0)}/${selected.length}` });
      res.end();
      return;
    }

    if (wantsObject(req)) {
      if (selected.length !== 1) {
        json(res, 406, { code: "PGRST116", message: "JSON object requested, multiple (or no) rows returned" });
        return;
      }
      json(res, 200, selected[0]);
      return;
    }

    json(res, 200, selected, {
      "content-range": `0-${Math.max(selected.length - 1, 0)}/${selected.length}`,
    });
    return;
  }

  if (req.method === "PATCH" && url.pathname === "/rest/v1/news") {
    const user = requireAdminMutation(req, res);
    if (!user) return;

    const selected = selectedNews(url);
    if (selected.length !== 1) {
      json(res, 404, { code: "PGRST116", message: "news row not found" });
      return;
    }
    const body = await readJson(req);
    Object.assign(selected[0], body);
    mutationEvents.push({ method: "PATCH", id: selected[0].id, user_id: user.id });
    json(res, 200, []);
    return;
  }

  if (req.method === "DELETE" && url.pathname === "/rest/v1/news") {
    const user = requireAdminMutation(req, res);
    if (!user) return;

    const selected = selectedNews(url);
    if (selected.length !== 1) {
      json(res, 404, { code: "PGRST116", message: "news row not found" });
      return;
    }
    const id = selected[0].id;
    news = news.filter((item) => item.id !== id);
    mutationEvents.push({ method: "DELETE", id, user_id: user.id });
    json(res, 200, []);
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
