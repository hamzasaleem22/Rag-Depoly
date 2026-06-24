import { createFileRoute } from "@tanstack/react-router";
import { createPortal } from "react-dom";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  Send,
  Bot,
  Sparkles,
  Plus,
  Square,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  Download,
  Key,
  Eye,
  EyeOff,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { toast } from "sonner";


export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Microsoft Annual 2025 Report RAG Chatbot" },
      { name: "description", content: "RAG-powered chatbot for the Microsoft Annual 2025 Report." },
    ],
  }),
  component: Index,
});

const API_URL = "http://localhost:8000/chat";

// localStorage is unavailable during SSR (Node.js). Always guard with this helper.
const getStoredKey = (): string =>
  typeof window !== "undefined" ? localStorage.getItem("llm_api_key") ?? "" : "";

/** Detect provider name from key prefix — mirrors the backend logic. */
const detectProvider = (key: string): string | null => {
  if (!key) return null;
  if (key.startsWith("AIza")) return "Google Gemini";
  if (key.startsWith("sk-ant-")) return "Anthropic Claude";
  if (key.startsWith("sk-")) return "OpenAI";
  return null;
};

const PROVIDER_COLORS: Record<string, string> = {
  google: "bg-blue-500/20 text-blue-400 border-blue-500/40",
  anthropic: "bg-orange-500/20 text-orange-400 border-orange-500/40",
  openai: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
};

type Feedback = "up" | "down" | null;
type Message = {
  id: string;
  role: "user" | "bot" | "error";
  content: string;
  timestamp: Date;
  feedback?: Feedback;
  provider?: string | null;
};

const formatTime = (d: Date) =>
  d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });


function Index() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiKey, setApiKey] = useState(() => getStoredKey());
  const [showApiKey, setShowApiKey] = useState(false);
  const [showKeyText, setShowKeyText] = useState(false);
  const [apiKeyDraft, setApiKeyDraft] = useState(() => getStoredKey());
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const keyBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [input]);

  const send = async (question: string, replaceLastBot = false) => {
    if (!question || loading) return;

    if (!replaceLastBot) {
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "user", content: question, timestamp: new Date() },
      ]);
    }
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      if (!API_URL) {
        throw new Error("Backend URL not configured. Set VITE_CHAT_API_URL.");
      }
      const body: Record<string, unknown> = { question };
      if (apiKey.trim()) body.api_key = apiKey.trim();
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok) {
        // Try to extract the structured detail message from the backend.
        let errMsg = `Request failed: ${res.status}`;
        try {
          const errData = await res.json();
          if (errData?.detail) errMsg = errData.detail;
        } catch (_) { /* ignore parse errors */ }
        throw new Error(errMsg);
      }
      const data = await res.json();
      const reply =
        typeof data === "string"
          ? data
          : data.answer ?? data.response ?? data.reply ?? data.message ?? JSON.stringify(data);
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "bot",
          content: String(reply),
          timestamp: new Date(),
          feedback: null,
          provider: data.provider ?? null,
        },
      ]);
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: "error",
            content: "Generation stopped.",
            timestamp: new Date(),
          },
        ]);
      } else {
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: "error",
            content: err instanceof Error ? err.message : "Something went wrong.",
            timestamp: new Date(),
          },
        ]);
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(input.trim());
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input.trim());
    }
  };

  const stop = () => abortRef.current?.abort();

  const regenerate = () => {
    // find the last user message
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    // Remove last bot/error after last user
    const idx = messages.lastIndexOf(lastUser);
    setMessages(messages.slice(0, idx + 1));
    void send(lastUser.content, true);
  };

  const setFeedback = (id: string, fb: Feedback) => {
    setMessages((m) =>
      m.map((msg) => (msg.id === id ? { ...msg, feedback: msg.feedback === fb ? null : fb } : msg)),
    );
    toast.success(fb === "up" ? "Thanks for the feedback!" : "Got it, we'll improve.");
  };

  const exportChat = () => {
    if (messages.length === 0) {
      toast.error("Nothing to export yet.");
      return;
    }
    const md = messages
      .map((m) => {
        const who = m.role === "user" ? "**You**" : m.role === "bot" ? "**Assistant**" : "**Error**";
        return `### ${who} · ${formatTime(m.timestamp)}\n\n${m.content}\n`;
      })
      .join("\n---\n\n");
    const header = `# Microsoft Annual 2025 — Chat Transcript\n\n_Exported ${new Date().toLocaleString()}_\n\n`;
    const blob = new Blob([header + md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `msft-rag-chat-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Transcript downloaded.");
  };

  const newChat = () => {
    stop();
    setMessages([]);
    setInput("");
    textareaRef.current?.focus();
  };

  return (
    <div className="relative flex h-screen w-full overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 aurora-bg" />
      <div className="pointer-events-none absolute inset-0 grid-overlay opacity-60" />

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex items-center justify-between border-b border-border bg-card/70 px-4 py-3 backdrop-blur-xl md:px-6">
          <div className="flex items-center gap-3">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl brand-gradient shadow-lg shadow-primary/30">
              <Bot className="h-5 w-5 text-primary-foreground" />
              <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-card bg-emerald-400 shadow-[0_0_8px_rgba(74,222,128,0.9)]" />
            </div>
            <div className="leading-tight">
              <h1 className="font-display text-base font-extrabold tracking-tight sm:text-lg">
                <span className="gradient-text">Microsoft Annual 2025</span>
              </h1>
              <div className="mt-0.5 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <span className="rounded-full bg-brand-cyan/40 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-foreground">
                  RAG
                </span>
                <span className="font-semibold text-emerald-600">● Online</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                ref={keyBtnRef}
                type="button"
                onClick={() => {
                  const next = !showApiKey;
                  setShowApiKey(next);
                  if (next) setApiKeyDraft(getStoredKey());
                }}
                title={apiKey ? "API key set" : "Set API key"}
                className={`flex h-9 w-9 items-center justify-center rounded-full border-2 transition-all hover:-translate-y-0.5 ${
                  apiKey
                    ? "border-emerald-500 bg-emerald-500/15 text-emerald-500"
                    : "border-border bg-card text-muted-foreground hover:border-brand-cyan"
                }`}
              >
                <Key className="h-4 w-4" />
              </button>
              {showApiKey && typeof window !== "undefined" && createPortal(
                <>
                  {/* Backdrop — closes popup on outside click */}
                  <div
                    className="fixed inset-0"
                    style={{ zIndex: 9998 }}
                    onClick={() => { setApiKeyDraft(apiKey); setShowApiKey(false); }}
                  />
                  {/* Popup panel — always on top of everything */}
                  <div
                    style={{
                      position: "fixed",
                      zIndex: 9999,
                      top: (keyBtnRef.current?.getBoundingClientRect().bottom ?? 48) + 8,
                      right: window.innerWidth - (keyBtnRef.current?.getBoundingClientRect().right ?? window.innerWidth - 16),
                    }}
                    className="w-80 rounded-2xl border-2 border-border bg-card p-4 shadow-2xl animate-fade-in-up"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <p className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      Your LLM API Key
                    </p>
                    {/* Live provider detection */}
                    {apiKeyDraft.trim() && (
                      <p className="mb-2 text-[11px] font-semibold">
                        Detected provider:{" "}
                        <span className="text-primary">
                          {detectProvider(apiKeyDraft.trim()) ?? "Unknown — check key format"}
                        </span>
                      </p>
                    )}
                    <div className="flex items-center gap-2">
                      <input
                        autoFocus
                        type={showKeyText ? "text" : "password"}
                        value={apiKeyDraft}
                        onChange={(e) => setApiKeyDraft(e.target.value)}
                      placeholder="AIzaSy… / sk-ant-… / sk-… (blank = server default)"
                        className="flex-1 rounded-xl border-2 border-border bg-background px-3 py-2 text-sm font-mono text-foreground placeholder:text-muted-foreground/50 outline-none transition-all focus:border-primary"
                      />
                      <button
                        type="button"
                        onClick={() => setShowKeyText(!showKeyText)}
                        className="flex h-9 w-9 items-center justify-center rounded-xl bg-muted text-muted-foreground hover:text-foreground transition-colors"
                        title={showKeyText ? "Hide key" : "Show key"}
                      >
                        {showKeyText ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          const trimmed = apiKeyDraft.trim();
                          setApiKey(trimmed);
                          if (typeof window !== "undefined") {
                            if (trimmed) {
                              localStorage.setItem("llm_api_key", trimmed);
                            } else {
                              localStorage.removeItem("llm_api_key");
                            }
                          }
                          setShowApiKey(false);
                          toast.success(trimmed ? "API key saved!" : "Using server default key.");
                        }}
                        className="flex-1 rounded-xl brand-gradient py-1.5 text-xs font-bold text-primary-foreground transition-all hover:opacity-90"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => { setApiKeyDraft(apiKey); setShowApiKey(false); }}
                        className="flex-1 rounded-xl border-2 border-border bg-muted py-1.5 text-xs font-bold text-muted-foreground transition-all hover:text-foreground"
                      >
                        Cancel
                      </button>
                    </div>
                    <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
                      Saved in your browser only. Supports Google Gemini (AIza…), Anthropic Claude (sk-ant-…), and OpenAI (sk-…). Leave blank to use the server's default.
                    </p>
                  </div>
                </>,
                document.body
              )}
            </div>
            {messages.length > 0 && (
              <button
                type="button"
                onClick={exportChat}
                title="Export chat as Markdown"
                className="hidden items-center gap-1.5 rounded-full border-2 border-border bg-card px-4 py-2 text-xs font-bold text-foreground transition-all hover:-translate-y-0.5 hover:border-brand-cyan hover:shadow-[0_10px_24px_-8px_oklch(0.78_0.15_200/0.7)] sm:flex"
              >
                <Download className="h-3.5 w-3.5" />
                Export
              </button>
            )}
            <button
              type="button"
              onClick={newChat}
              className="group flex items-center gap-1.5 rounded-full brand-gradient px-4 py-2 text-xs font-extrabold text-primary-foreground shadow-lg shadow-primary/40 transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/60"
            >
              <Plus className="h-3.5 w-3.5 transition-transform group-hover:rotate-90" />
              New Chat
            </button>
          </div>
        </header>


        {/* Chat area */}
        <main className="relative flex flex-1 flex-col overflow-hidden">
          <div ref={scrollRef} className="flex-1 overflow-y-auto">
            <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6 md:py-10">
              {messages.length === 0 && <EmptyState onPick={(q) => void send(q)} />}

              {messages.map((m) => (
                <MessageBubble
                  key={m.id}
                  message={m}
                  onCopy={() => {
                    void navigator.clipboard.writeText(m.content);
                    toast.success("Copied to clipboard");
                  }}
                  onRegenerate={regenerate}
                  onFeedback={(fb) => setFeedback(m.id, fb)}
                />
              ))}

              {loading && (
                <div className="flex items-end gap-3 animate-fade-in-up">
                  <Avatar role="bot" />
                  <div className="rounded-2xl rounded-bl-md border-2 border-border bg-card px-4 py-3.5 shadow-md">
                    <div className="flex gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-primary animate-bounce-dot" />
                      <span className="h-2 w-2 rounded-full bg-primary-glow animate-bounce-dot [animation-delay:0.15s]" />
                      <span className="h-2 w-2 rounded-full bg-brand-cyan animate-bounce-dot [animation-delay:0.3s]" />
                    </div>
                  </div>
                </div>
              )}

            </div>
          </div>

          {/* Composer */}
          <div className="border-t border-border bg-card/70 backdrop-blur-xl">
            <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl items-end gap-2 px-4 py-4">
              <div className="group relative flex-1">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about the 2025 report... (Shift+Enter for newline)"
                  disabled={loading}
                  className="w-full resize-none rounded-2xl border-2 border-border bg-card px-4 py-3.5 pr-14 font-sans text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground/70 outline-none transition-all focus:border-primary focus:shadow-[0_0_0_4px_oklch(0.66_0.25_5/0.18)] disabled:opacity-50"
                  style={{ maxHeight: 200 }}
                />
                <kbd className="pointer-events-none absolute right-3 bottom-3 hidden rounded-md border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground sm:inline">
                  ⏎
                </kbd>
              </div>
              {loading ? (
                <button
                  type="button"
                  onClick={stop}
                  className="flex h-[50px] items-center justify-center gap-2 rounded-2xl border-2 border-destructive bg-destructive/15 px-4 text-sm font-bold text-destructive transition-all hover:-translate-y-0.5 hover:bg-destructive/25"
                  title="Stop generation"
                >
                  <Square className="h-4 w-4 fill-current" />
                  <span className="hidden sm:inline">Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="group flex h-[50px] items-center justify-center gap-2 rounded-2xl brand-gradient px-5 text-sm font-bold text-primary-foreground shadow-lg shadow-primary/40 transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/50 disabled:opacity-40 disabled:hover:translate-y-0"
                >
                  <Send className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  <span className="hidden sm:inline">Send</span>
                </button>
              )}
            </form>
            <p className="pb-3 text-center text-[10px] font-medium text-muted-foreground">
              Grounded answers from Microsoft's 2025 annual report · Built by{" "}
              <span className="font-bold gradient-text">Hamza</span>
            </p>
          </div>

        </main>
      </div>
    </div>
  );
}

const SUGGESTED_PROMPTS = [
  { icon: "💰", label: "Revenue & Growth", q: "Summarize Microsoft's total revenue and year-over-year growth in fiscal 2025." },
  { icon: "☁️", label: "Azure & Cloud", q: "How did Azure and the Intelligent Cloud segment perform in 2025?" },
  { icon: "🤖", label: "AI Strategy", q: "What are Microsoft's key AI initiatives and Copilot milestones for 2025?" },
  { icon: "⚠️", label: "Risk Factors", q: "What are the most important risk factors highlighted in the 2025 annual report?" },
];

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="mt-8 flex flex-col items-center text-center md:mt-16">
      <div className="relative mb-6 flex h-20 w-20 items-center justify-center rounded-3xl brand-gradient shadow-[0_20px_60px_-15px_oklch(0.66_0.25_5/0.7)] animate-pulse-glow">
        <Sparkles className="h-9 w-9 text-primary-foreground drop-shadow" />
        <span className="absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-brand-cyan text-[10px] font-bold text-foreground shadow-md">
          AI
        </span>
      </div>
      <h2 className="font-display text-4xl font-extrabold tracking-tight md:text-5xl">
        <span className="gradient-text">Microsoft Annual 2025</span>
      </h2>
      <p className="mt-2 text-sm font-semibold uppercase tracking-[0.25em] text-primary">
        RAG Chatbot
      </p>
      <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
        Ask anything about Microsoft's 2025 annual report. I'll search the document and give you
        grounded, markdown-formatted answers.
      </p>

      <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
        {SUGGESTED_PROMPTS.map((p, i) => (
          <button
            key={p.label}
            type="button"
            onClick={() => onPick(p.q)}
            style={{ animationDelay: `${i * 80}ms` }}
            className="group relative overflow-hidden rounded-2xl border-2 border-border bg-card p-4 text-left transition-all hover:-translate-y-1 hover:border-primary hover:shadow-[0_18px_40px_-18px_oklch(0.66_0.25_5/0.55)] animate-fade-in-up"
          >
            <div className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br from-primary/20 to-brand-cyan/20 opacity-0 blur-2xl transition-opacity group-hover:opacity-100" />
            <div className="flex items-center gap-2">
              <span className="text-xl">{p.icon}</span>
              <span className="font-display text-sm font-extrabold text-foreground">{p.label}</span>
            </div>
            <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground line-clamp-2">
              {p.q}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}


function Avatar({ role }: { role: "user" | "bot" }) {
  if (role === "bot") {
    return (
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl brand-gradient shadow-md shadow-primary/40 ring-2 ring-card">
        <Bot className="h-4 w-4 text-primary-foreground" />
      </div>
    );
  }
  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-cyan to-brand-violet font-mono text-[11px] font-extrabold text-white shadow-md ring-2 ring-card">
      YOU
    </div>
  );
}


function MessageBubble({
  message,
  onCopy,
  onRegenerate,
  onFeedback,
}: {
  message: Message;
  onCopy: () => void;
  onRegenerate: () => void;
  onFeedback: (fb: Feedback) => void;
}) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const isError = message.role === "error";
  const isBot = message.role === "bot";

  const handleCopy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div
      className={`group/msg flex flex-col gap-1 animate-fade-in-up ${
        isUser ? "items-end" : "items-start"
      }`}
    >
      <div className={`flex w-full items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
        <Avatar role={isUser ? "user" : "bot"} />
        <div
          className={`max-w-[82%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed ${
            isUser
              ? "rounded-tr-sm brand-gradient text-primary-foreground shadow-lg shadow-primary/40"
              : isError
                ? "rounded-tl-sm border-2 border-destructive bg-destructive/10 text-destructive font-medium"
                : "rounded-tl-sm border-2 border-border bg-card text-foreground shadow-md"
          }`}
        >

          {isUser || isError ? (
            <p className="whitespace-pre-wrap font-sans">{message.content}</p>
          ) : (
            <div className="md-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>

      <div
        className={`flex items-center gap-1 px-11 transition-opacity ${
          isUser ? "flex-row-reverse" : ""
        } ${isBot ? "opacity-0 group-hover/msg:opacity-100" : ""}`}
      >
        <span className="font-mono text-[10px] text-muted-foreground/60">
          {formatTime(message.timestamp)}
        </span>
        {isBot && message.provider && (
          <span
            className={`ml-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
              PROVIDER_COLORS[message.provider] ?? "bg-muted text-muted-foreground border-border"
            }`}
          >
            {message.provider === "google"
              ? "Gemini"
              : message.provider === "anthropic"
              ? "Claude"
              : message.provider === "openai"
              ? "OpenAI"
              : message.provider}
          </span>
        )}

        {isBot && (
          <div className="ml-2 flex items-center gap-0.5">
            <ActionBtn title="Copy" onClick={handleCopy}>
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            </ActionBtn>
            <ActionBtn title="Regenerate" onClick={onRegenerate}>
              <RefreshCw className="h-3 w-3" />
            </ActionBtn>
            <ActionBtn
              title="Good response"
              onClick={() => onFeedback("up")}
              active={message.feedback === "up"}
            >
              <ThumbsUp className="h-3 w-3" />
            </ActionBtn>
            <ActionBtn
              title="Bad response"
              onClick={() => onFeedback("down")}
              active={message.feedback === "down"}
            >
              <ThumbsDown className="h-3 w-3" />
            </ActionBtn>
          </div>
        )}
      </div>
    </div>
  );
}

function ActionBtn({
  children,
  onClick,
  title,
  active,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`flex h-7 w-7 items-center justify-center rounded-lg border border-transparent text-muted-foreground transition-all hover:scale-110 hover:border-border hover:bg-card hover:text-primary hover:shadow-md ${
        active ? "border-primary bg-primary/15 text-primary scale-110" : ""
      }`}
    >
      {children}
    </button>

  );
}
