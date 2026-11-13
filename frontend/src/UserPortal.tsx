import { useCallback, useEffect, useRef, useState } from "react";
import { AttachmentPicker, attachmentBase64 } from "./AttachmentPicker";
import { request } from "./api";
import { useWorkspace } from "./workspace";

type Conversation = { id: string; title: string; created_at: string; updated_at: string };
type Message = { id: string; role: "user" | "assistant"; content: string; decision: string };
type Detail = Conversation & { messages: Message[] };

const SUBMITTED_PLACEHOLDER = "Request submitted";
const STORED_ATTACHMENT = /(?:^|\n\n)Attachment: (PDF|DOCX|TXT) document$/;

// Server history holds only governed text; withheld prompts keep a placeholder that is explained here.
function userMessageView(message: Message, sessionFilename?: string) {
  const stored = STORED_ATTACHMENT.exec(message.content);
  const body = stored ? message.content.slice(0, stored.index) : message.content;
  const attachment = sessionFilename ?? (stored ? `${stored[1]} document` : undefined);
  if (body !== SUBMITTED_PLACEHOLDER) return { body, attachment, withheld: false };
  const reason = message.decision === "BLOCK" ? "Your message was withheld by a governance policy and isn't shown."
    : message.decision === "HUMAN_REVIEW" ? "Your message is held for review and isn't shown."
      : "Your message isn't shown.";
  return { body: reason, attachment, withheld: true };
}

export function UserPortal({ account, onSignOut, sessionError }: { account: string; onSignOut: () => Promise<void>; sessionError: string }) {
  const workspace = useWorkspace();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [moreAvailable, setMoreAvailable] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  // Filenames chosen in this browser session only; never sent to history or browser storage.
  const [sessionFilenames, setSessionFilenames] = useState<Record<string, string>>({});
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const [signingOut, setSigningOut] = useState(false);

  const loadList = useCallback(async () => {
    const rows = await request<Conversation[]>("/api/chat/conversations?offset=0&limit=100");
    setConversations(rows);
    setMoreAvailable(rows.length === 100);
    return rows;
  }, []);
  const openConversation = useCallback(async (id: string) => {
    setLoadingConversation(true); setHistoryError("");
    try {
      const detail = await request<Detail>(`/api/chat/conversations/${id}`);
      setSelectedId(detail.id); setMessages(detail.messages);
    } catch { setHistoryError("Conversation could not be loaded. Please try again."); }
    finally { setLoadingConversation(false); }
  }, []);
  useEffect(() => {
    let active = true;
    setLoadingHistory(true);
    void request<Conversation[]>("/api/chat/conversations?offset=0&limit=100")
      .then(async rows => {
        if (!active) return;
        setConversations(rows);
        setMoreAvailable(rows.length === 100);
        if (rows.length) {
          try {
            const detail = await request<Detail>(`/api/chat/conversations/${rows[0].id}`);
            if (active) { setSelectedId(detail.id); setMessages(detail.messages); }
          } catch { if (active) setHistoryError("Conversation could not be loaded. Please try again."); }
        }
      })
      .catch(() => { if (active) setHistoryError("Conversation history is unavailable. Please try again."); })
      .finally(() => { if (active) setLoadingHistory(false); });
    return () => { active = false; };
  }, [account]);

  async function newChat() {
    setHistoryError("");
    try {
      const created = await request<Conversation>("/api/chat/conversations", "POST");
      setSelectedId(created.id); setMessages([]);
      await loadList();
    } catch { setHistoryError("A new conversation could not be started. Please try again."); }
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current || !workspace.data || workspace.loading || (!text.trim() && !file)) return;
    inFlight.current = true; setBusy(true); setError("");
    try {
      let conversationId = selectedId;
      if (!conversationId) {
        const created = await request<Conversation>("/api/chat/conversations", "POST");
        conversationId = created.id; setSelectedId(created.id);
      }
      const attachment = file ? { filename: file.name, content_type: file.type, content_base64: await attachmentBase64(file) } : {};
      const multi = workspace.data.mode === "MULTI";
      const prefix = multi ? "/api/v2" : "/api";
      await request(`${prefix}/governance/${file ? "generate-document" : "generate"}`, "POST",
        { text, ...attachment, conversation_id: conversationId },
        multi ? { headers: { "If-Match": `"${workspace.data.set_revision}"` } } : {});
      const detail = await request<Detail>(`/api/chat/conversations/${conversationId}`);
      const sent = file ? detail.messages.filter(message => message.role === "user").at(-1) : undefined;
      if (sent && file) setSessionFilenames(previous => ({ ...previous, [sent.id]: file.name }));
      setMessages(detail.messages); await loadList();
      setText(""); setFile(null);
    } catch { setError("We couldn't complete that request. Please try again."); await workspace.reload(); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <div className="user-chat-shell">
    <header className="user-chat-header"><div><strong>Governed AI Chat</strong><p>Signed in as {account}</p></div>
      <button disabled={signingOut} onClick={async () => { setSigningOut(true); try { await onSignOut(); } finally { setSigningOut(false); } }}>Sign out</button>
    </header>
    <div className="user-chat-layout">
      <aside className="user-chat-sidebar" aria-label="Conversation history">
        <button className="primary" disabled={busy || loadingHistory} onClick={() => void newChat()}>New chat</button>
        <h2>Previous conversations</h2>
        {loadingHistory && <p role="status">Loading conversations…</p>}
        {historyError && <p role="alert">{historyError} <button onClick={() => void loadList().then(() => setHistoryError("")).catch(() => setHistoryError("Conversation history is unavailable. Please try again."))}>Retry</button></p>}
        {!loadingHistory && !historyError && !conversations.length && <p>No conversations yet.</p>}
        <nav aria-label="Previous conversations">{conversations.map(conversation => <button
          className={selectedId === conversation.id ? "selected" : ""} key={conversation.id}
          disabled={busy || loadingConversation} onClick={() => void openConversation(conversation.id)}>
          <span>{conversation.title}</span><small>{new Date(conversation.updated_at).toLocaleString()}</small>
        </button>)}</nav>
        {moreAvailable && <button disabled={loadingHistory || busy} onClick={() => {
          void request<Conversation[]>(`/api/chat/conversations?offset=${conversations.length}&limit=100`)
            .then(rows => { setConversations(previous => [...previous, ...rows]); setMoreAvailable(rows.length === 100); })
            .catch(() => setHistoryError("More conversations could not be loaded. Please try again."));
        }}>Load more</button>}
      </aside>
      <main className="user-chat-main">
        <h1>Your AI assistant</h1>
        {sessionError && <p role="alert">{sessionError}</p>}
        <section className="user-conversation" aria-label="Conversation">
          {loadingConversation && <p role="status">Loading conversation…</p>}
          {!loadingConversation && !messages.length && <p>Ask a question to start this conversation.</p>}
          {messages.map(message => {
            if (message.role === "assistant") return <article className="chat-message chat-message-assistant" key={message.id}>
              <strong>Assistant</strong><p>{message.content}</p>
            </article>;
            const view = userMessageView(message, sessionFilenames[message.id]);
            return <article className="chat-message chat-message-user" key={message.id}>
              <strong>You</strong><p className={view.withheld ? "chat-message-withheld" : undefined}>{view.body}</p>
              {view.attachment && <p className="chat-attachment">Attachment: {view.attachment}</p>}
            </article>;
          })}
        </section>
        <form className="panel user-chat-composer" onSubmit={send}>
          <label htmlFor="chat-prompt">Message<textarea id="chat-prompt" value={text} disabled={busy} maxLength={12000}
            required={!file} onChange={event => setText(event.target.value)} placeholder="Ask a question" /></label>
          <AttachmentPicker file={file} disabled={busy} onChange={setFile} />
          {workspace.error && <p role="alert">Request readiness is unavailable. Please try again.</p>}
          {error && <p role="alert">{error}</p>}
          {workspace.loading && <p role="status">Checking request readiness…</p>}
          <div className="actions"><button className="primary" disabled={busy || loadingHistory || workspace.loading || !workspace.data || (!text.trim() && !file)}>{busy ? "Processing…" : "Send message"}</button></div>
        </form>
      </main>
    </div>
  </div>;
}
