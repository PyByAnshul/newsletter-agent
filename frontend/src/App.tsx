import { useRef, useState } from "react"
import { marked } from "marked"
import { Check, Circle, Loader2, TriangleAlert, UserCheck } from "lucide-react"
import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtItem,
  ChainOfThoughtStep,
  ChainOfThoughtTrigger,
} from "@/components/prompt-kit/chain-of-thought"

const API = "https://newsletter-agent.fastapicloud.dev"

type Mode = "autonomous" | "human"
type Status = "pending" | "active" | "done"
type Step = { id: string; label: string; desc: string; status: Status; output?: unknown }
type Result = {
  subject: string
  newsletter: string
  output_path: string
  sent: boolean
  revision_count: number
  format: string
}
type Draft = {
  subject: string
  newsletter: string
  review_feedback: string
  review_score: number | null
}

// Render a node's JSON output as readable lines instead of a raw blob.
function StepOutput({ output }: { output: unknown }) {
  if (output == null) return <span className="text-muted-foreground">no output</span>
  if (typeof output !== "object") return <span>{String(output)}</span>

  return (
    <div className="space-y-1.5">
      {Object.entries(output as Record<string, unknown>).map(([key, val]) => (
        <div key={key}>
          <span className="text-foreground font-medium">{key}: </span>
          {key === "articles" && Array.isArray(val) ? (
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              {val.map((a, i) => {
                const art = a as { title?: string; summary?: string; url?: string }
                return (
                  <li key={i}>
                    <span className="text-foreground">{art.title}</span>
                    {art.summary ? ` — ${art.summary}` : ""}
                  </li>
                )
              })}
            </ul>
          ) : (
            <span>{typeof val === "object" ? JSON.stringify(val) : String(val)}</span>
          )}
        </div>
      ))}
    </div>
  )
}

function StepIcon({ status }: { status: Status }) {
  if (status === "done") return <Check className="text-primary size-4" />
  if (status === "active") return <Loader2 className="text-primary size-4 animate-spin" />
  return <Circle className="size-2 fill-current" />
}

export default function App() {
  const [goal, setGoal] = useState(
    "Create a weekly newsletter on the latest AI agent news."
  )
  const [mode, setMode] = useState<Mode>("autonomous")
  const [steps, setSteps] = useState<Step[]>([])
  const [result, setResult] = useState<Result | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [threadId, setThreadId] = useState("")
  const [feedback, setFeedback] = useState("")
  const [error, setError] = useState("")
  const [running, setRunning] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  // Attach the shared event handlers to any /run or /resume stream.
  function bind(es: EventSource) {
    es.addEventListener("steps", (e) => {
      const list = JSON.parse((e as MessageEvent).data) as Omit<Step, "status">[]
      setSteps(list.map((s, i) => ({ ...s, status: i === 0 ? "active" : "pending" })))
    })

    es.addEventListener("step", (e) => {
      const { id, output } = JSON.parse((e as MessageEvent).data)
      // Mark this node done (loops re-fire the same id -> refresh its output),
      // then light up the first still-pending step.
      setSteps((prev) => {
        const marked = prev.map((s) =>
          s.id === id ? { ...s, status: "done" as Status, output } : s
        )
        const nextPending = marked.findIndex((s) => s.status === "pending")
        return marked.map((s, i) =>
          i === nextPending ? { ...s, status: "active" as Status } : s
        )
      })
    })

    es.addEventListener("interrupt", (e) => {
      const { thread_id, draft } = JSON.parse((e as MessageEvent).data)
      setThreadId(thread_id)
      setDraft(draft)
      setRunning(false)
      setSteps((prev) =>
        prev.map((s) =>
          s.id === "human_gate" ? { ...s, status: "active" } : s
        )
      )
      es.close()
    })

    es.addEventListener("done", (e) => {
      setResult(JSON.parse((e as MessageEvent).data))
      setDraft(null)
      setRunning(false)
      setSteps((prev) => prev.map((s) => ({ ...s, status: "done" })))
      es.close()
    })

    es.addEventListener("error", (e) => {
      const msg = (e as MessageEvent).data
      setError(msg ? JSON.parse(msg).message : "Connection to backend lost.")
      setRunning(false)
      es.close()
    })
  }

  function run() {
    if (running || !goal.trim()) return
    esRef.current?.close()
    setSteps([])
    setResult(null)
    setDraft(null)
    setError("")
    setFeedback("")
    setRunning(true)

    const es = new EventSource(
      `${API}/run?goal=${encodeURIComponent(goal)}&mode=${mode}`
    )
    esRef.current = es
    bind(es)
  }

  function resume(approved: boolean) {
    if (!threadId) return
    setRunning(true)
    setDraft(null)
    const es = new EventSource(
      `${API}/resume?thread_id=${threadId}&approved=${approved}` +
        `&feedback=${encodeURIComponent(feedback)}`
    )
    esRef.current = es
    bind(es)
    setFeedback("")
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Newsletter Agent</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Watch the agent plan, research, summarize, write, review — and revise.
        </p>
      </header>

      {/* Mode toggle */}
      <div className="mb-4 inline-flex rounded-lg border border-border bg-card p-1 text-sm">
        {(["autonomous", "human"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => !running && setMode(m)}
            disabled={running}
            className={
              "rounded-md px-3 py-1.5 font-medium capitalize transition-colors disabled:opacity-60 " +
              (mode === m
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground")
            }
          >
            {m === "human" ? "Human in the loop" : "Fully autonomous"}
          </button>
        ))}
      </div>

      <div className="bg-card border-border rounded-xl border p-2 shadow-sm">
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run()
          }}
          rows={2}
          placeholder="Describe the newsletter you want…"
          className="placeholder:text-muted-foreground w-full resize-none bg-transparent px-3 py-2 text-sm outline-none"
        />
        <div className="flex items-center justify-between px-1 pb-1">
          <span className="text-muted-foreground text-xs">⌘/Ctrl + Enter to run</span>
          <button
            onClick={run}
            disabled={running || !goal.trim()}
            className="bg-primary text-primary-foreground inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {running && <Loader2 className="size-4 animate-spin" />}
            {running ? "Running…" : "Generate"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-6 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <TriangleAlert className="size-4" /> {error}
        </div>
      )}

      {steps.length > 0 && (
        <div className="bg-card border-border mt-6 rounded-xl border p-5 shadow-sm">
          <ChainOfThought>
            {steps.map((step) => (
              <ChainOfThoughtStep key={step.id} defaultOpen={step.status !== "pending"}>
                <ChainOfThoughtTrigger
                  leftIcon={<StepIcon status={step.status} />}
                  className={
                    step.status === "active"
                      ? "text-foreground font-medium"
                      : step.status === "done"
                        ? "text-foreground"
                        : ""
                  }
                >
                  {step.label}
                  <span className="text-muted-foreground ml-2 text-xs font-normal">
                    {step.desc}
                  </span>
                </ChainOfThoughtTrigger>
                <ChainOfThoughtContent>
                  <ChainOfThoughtItem>
                    {step.status === "done" ? (
                      <StepOutput output={step.output} />
                    ) : step.status === "active" ? (
                      "Working…"
                    ) : (
                      "Waiting…"
                    )}
                  </ChainOfThoughtItem>
                </ChainOfThoughtContent>
              </ChainOfThoughtStep>
            ))}
          </ChainOfThought>
        </div>
      )}

      {/* Human-in-the-loop approval gate */}
      {draft && (
        <div className="mt-6 rounded-xl border border-primary/30 bg-primary/5 p-6 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <UserCheck className="text-primary size-5" />
            <h2 className="text-lg font-semibold">Your review</h2>
            {draft.review_score != null && (
              <span className="text-muted-foreground ml-auto text-xs">
                reviewer score: {draft.review_score}/10
              </span>
            )}
          </div>
          {draft.review_feedback && (
            <p className="text-muted-foreground mb-3 text-sm italic">
              Agent's self-critique: {draft.review_feedback}
            </p>
          )}
          <div className="mb-3 max-h-64 overflow-auto rounded-lg border border-border bg-card p-4">
            <div className="mb-2 font-semibold">{draft.subject}</div>
            <div
              className="newsletter-body text-foreground/90 text-sm"
              dangerouslySetInnerHTML={{
                __html: marked.parse(draft.newsletter, { async: false }) as string,
              }}
            />
          </div>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            rows={2}
            placeholder="Optional: what should change? (leave empty to just approve)"
            className="placeholder:text-muted-foreground border-border mb-3 w-full resize-none rounded-lg border bg-card px-3 py-2 text-sm outline-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => resume(true)}
              className="bg-primary text-primary-foreground rounded-lg px-4 py-2 text-sm font-medium"
            >
              Approve & send
            </button>
            <button
              onClick={() => resume(false)}
              disabled={!feedback.trim()}
              className="border-border rounded-lg border px-4 py-2 text-sm font-medium disabled:opacity-50"
            >
              Request changes
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="bg-card border-border mt-6 rounded-xl border p-6 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <Check className="text-primary size-5" />
            <h2 className="text-lg font-semibold">{result.subject || "Newsletter"}</h2>
            {result.revision_count > 1 && (
              <span className="text-muted-foreground ml-auto text-xs">
                {result.revision_count} revisions
              </span>
            )}
          </div>
          <div
            className="newsletter-body text-foreground/90 text-sm"
            dangerouslySetInnerHTML={{
              __html:
                result.format === "html"
                  ? result.newsletter
                  : (marked.parse(result.newsletter, { async: false }) as string),
            }}
          />
          {result.output_path && (
            <p className="text-muted-foreground mt-4 text-xs">
              {result.sent ? "Sent (simulated) — saved to " : "Saved to "}
              {result.output_path}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
