// Opt in with GOVERNANCE_TEST_PYTHON to exercise the real local API, never cloud services.
import { spawn } from "node:child_process";
import { access } from "node:fs/promises";
import { createServer } from "node:net";
import { resolve } from "node:path";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
const python = process.env.GOVERNANCE_TEST_PYTHON;
describe.skipIf(!python)("React to disposable FastAPI integration", () => {
  let child;
  let address = "";
  let sessionCookie = "";
  let csrf = "";
  let networkFetch;
  let credentialFile = "";
  let App;
  beforeAll(async () => {
    const port = await new Promise((done, fail) => {
      const listener = createServer();
      listener.on("error", fail);
      listener.listen(0, "127.0.0.1", () => {
        const selected = listener.address();
        if (!selected || typeof selected === "string")
          return fail(new Error("No disposable port"));
        listener.close(() => done(selected.port));
      });
    });
    address = `http://127.0.0.1:${port}`;
    const root = resolve(process.cwd(), "..");
    child = spawn(
      python,
      [
        "-B",
        resolve(root, "backend/tests/sso_integration_server.py"),
        "--port",
        String(port),
      ],
      {
        cwd: root,
        env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    // Consume logs without emitting credentials or provider payloads into test output.
    child.stderr?.on("data", () => {});
    const state = await new Promise((done, fail) => {
      let text = "";
      const timer = setTimeout(
        () => fail(new Error("Disposable backend startup timed out")),
        15000,
      );
      child.once("error", () => {
        clearTimeout(timer);
        fail(new Error("Cannot start disposable backend"));
      });
      child.once("exit", () => {
        clearTimeout(timer);
        fail(new Error("Disposable backend exited"));
      });
      child.stdout?.on("data", (part) => {
        text += part.toString();
        while (text.includes("\n")) {
          const end = text.indexOf("\n");
          const line = text.slice(0, end);
          text = text.slice(end + 1);
          if (!line.startsWith("{")) continue;
          const parsed = JSON.parse(line);
          if (parsed.mode === "DISPOSABLE_LOCAL_FIXTURE") {
            clearTimeout(timer);
            done(parsed);
            return;
          }
        }
      });
    });
    credentialFile = state.credential_file;

    const deadline = Date.now() + 10000;
    while (true) {
      try {
        if ((await fetch(address + "/health")).ok) break;
      } catch {
        /* Startup only; no mutations retried. */
      }
      if (Date.now() >= deadline)
        throw new Error("Disposable backend was not ready");
      await new Promise((done) => setTimeout(done, 50));
    }
    // Node fetch has no browser cookie jar. Retain only synthetic fixture cookies
    // in this test transport; production still enforces Secure cookies over HTTPS.
    networkFetch = globalThis.fetch.bind(globalThis);
    const started = await networkFetch(address + "/api/sso/login", {
      redirect: "manual",
    });
    const binding = started.headers.get("set-cookie").split(";")[0];
    const stateValue = new URL(
      started.headers.get("location"),
    ).searchParams.get("state");
    const callback = await networkFetch(
      address +
        "/api/sso/callback?" +
        new URLSearchParams({ state: stateValue, code: "synthetic-code" }),
      {
        redirect: "manual",
        headers: { Cookie: binding },
      },
    );
    expect(callback.status).toBe(303);
    sessionCookie = callback.headers.get("set-cookie").split(";")[0];
    const me = await networkFetch(address + "/api/sso/me", {
      headers: { Cookie: sessionCookie },
    });
    csrf = (await me.json()).csrf_token;
    vi.stubEnv("VITE_API_URL", address);
    App = (await import("./main")).App;
  }, 30000);
  afterEach(() => {
    cleanup();
    sessionStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    window.history.replaceState({}, "", "/");
  });
  afterAll(async () => {
    sessionCookie = "";
    csrf = "";
    if (child && child.exitCode === null && child.signalCode === null) {
      await new Promise((done) => {
        const timer = setTimeout(() => {
          child.kill("SIGKILL");
          done();
        }, 5000);
        child.once("exit", () => {
          clearTimeout(timer);
          done();
        });
        child.kill("SIGTERM");
      });
    }
    if (credentialFile)
      await expect(access(credentialFile)).rejects.toMatchObject({
        code: "ENOENT",
      });
  });
  it("completes policy, simulation, decisions, review, feedback and failed offline export through existing screens", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    window.history.replaceState({}, "", "/");
    const preflight = await fetch(address + "/api/policies", {
      method: "OPTIONS",
      headers: {
        Origin: "http://localhost:5174",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
      },
    });
    expect(preflight.status).toBe(200);
    expect(preflight.headers.get("access-control-allow-origin")).toBe(
      "http://localhost:5174",
    );
    const deniedOrigin = await fetch(address + "/api/policies", {
      method: "OPTIONS",
      headers: {
        Origin: "http://127.0.0.1:5174",
        "Access-Control-Request-Method": "POST",
      },
    });
    expect(deniedOrigin.status).toBe(400);
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options = {}) =>
      networkFetch(url, {
        ...options,
        headers: {
          ...options.headers,
          Cookie: sessionCookie,
          Origin: "https://testserver",
          "X-CSRF-Token": csrf,
        },
      }),
    );
    render(<App />);
    await screen.findByRole("heading", {
      name: "Your governance, at a glance",
    });
    async function policies() {
      fireEvent.click(screen.getByRole("link", { name: "Policy management" }));
      await screen.findByRole("heading", { name: "Policy management" });
    }
    async function lifecycle() {
      for (const operation of ["submit", "approve", "publish", "activate"]) {
        fireEvent.click(await screen.findByRole("button", { name: operation }));
        await screen.findByText(`Policy ${operation} completed.`);
      }
    }
    await policies();
    fireEvent.click(await screen.findByRole("link", { name: "Create policy" }));
    fireEvent.change(await screen.findByLabelText("Policy name"), {
      target: { value: "Offline UI protection" },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await screen.findByRole("link", { name: "Offline UI protection" });
    fireEvent.click(screen.getByRole("link", { name: "View / edit" }));
    fireEvent.change(await screen.findByLabelText("Policy name"), {
      target: { value: "Offline UI protection revised" },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await screen.findByRole("link", { name: "Offline UI protection revised" });
    await lifecycle();
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    await screen.findByRole("heading", { name: "Immutable version history" });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(screen.getByRole("button", { name: "disable" }));
    await screen.findByText("Policy disable completed.");
    fireEvent.click(screen.getByRole("button", { name: "enable" }));
    await screen.findByText("Policy enable completed.");
    fireEvent.click(screen.getByRole("link", { name: "Policy simulator" }));
    const option = await screen.findByRole("option", {
      name: "Offline UI protection revised",
    });
    fireEvent.change(screen.getByLabelText("Policy draft"), {
      target: { value: option.value },
    });
    fireEvent.change(screen.getByLabelText("Sample prompt"), {
      target: { value: "Safe synthetic text" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Simulate policy" }));
    await screen.findByRole("heading", { name: "Simulation results" });
    expect(screen.getByText("ALLOW", { exact: true })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "AI playground" }));
    for (const [text, decision] of [
      ["Safe synthetic text", "ALLOW"],
      ["api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345", "BLOCK"],
      ["Contact test.person@example.com", "REDACT"],
      ["[OUTPUT_SECRET]", "BLOCK"],
    ]) {
      fireEvent.change(screen.getByLabelText("User prompt"), {
        target: { value: text },
      });
      fireEvent.click(
        screen.getByRole("button", { name: /Run governed request/ }),
      );
      await screen.findByText(`Final decision: ${decision}`);
      if (decision === "ALLOW") {
        expect(screen.getByText("LOCAL TEST FIXTURE")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "3" }));
        await screen.findByText("Feedback saved.");
      }
      if (decision === "BLOCK")
        expect(screen.getByText(/Response withheld/)).toBeInTheDocument();
    }
    await policies();
    fireEvent.click(await screen.findByRole("link", { name: "View / edit" }));
    fireEvent.change(await screen.findByLabelText("blocked_keywords action"), {
      target: { value: "HUMAN_REVIEW" },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await screen.findByRole("heading", { name: "Policy management" });
    await lifecycle();
    fireEvent.click(screen.getByRole("link", { name: "AI playground" }));
    fireEvent.change(screen.getByLabelText("User prompt"), {
      target: { value: "internal-only" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Run governed request/ }),
    );
    await screen.findByText("Final decision: HUMAN_REVIEW");
    fireEvent.click(screen.getByRole("link", { name: "Human review" }));
    fireEvent.click(await screen.findByRole("button", { name: "approve" }));
    await screen.findByText("APPROVED RESUBMIT REQUIRED");
    fireEvent.click(screen.getByRole("link", { name: "Validation history" }));
    await screen.findAllByRole("button", { name: "Inspect metadata" });
    fireEvent.click(screen.getByRole("link", { name: "Audit & reports" }));
    await screen.findByRole("heading", { name: "History date filter" });
    expect(screen.queryByRole("button", { name: "Export JSON" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Export CSV" })).toBeNull();
    const exported = await fetch(address + "/api/reports/export", {
      method: "POST", headers: { Cookie: sessionCookie, "Content-Type": "application/json", "X-CSRF-Token": csrf, Origin: "https://testserver" },
      body: JSON.stringify({ format: "json" }),
    });
    expect(exported.status).toBe(201);
    expect((await exported.json()).status).toBe("FAILED");
    const feedback = await fetch(address + "/api/feedback/summary", {
      headers: { Cookie: sessionCookie },
    });
    expect(await feedback.json()).toEqual({ count: 1, average: 3 });
    const summary = await fetch(address + "/api/analytics/overview", {
      headers: { Cookie: sessionCookie },
    });
    expect((await summary.json()).total_validations).toBe(5);
    fireEvent.click(screen.getByRole("link", { name: "Overview" }));
    await screen.findByRole("heading", {
      name: "Your governance, at a glance",
    });
    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
    );
  }, 30000);
});
