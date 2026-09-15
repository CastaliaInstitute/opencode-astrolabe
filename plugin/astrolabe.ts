import type { Plugin } from "@opencode-ai/plugin"

type SessionState = {
  title?: string
  status?: string
  agent?: string
  model?: string
  provider?: string
  task?: string
  partType?: string
  partState?: string
  step: number
}

export default (async ({ directory }) => {
  const settings = {
    enabled: false,
    url: "http://127.0.0.1:8090",
    path: "/",
    minInterval: 250,
  }
  let emoji = ""
  const projectName = directory.split(/[\\/]/).filter(Boolean).pop() ?? directory

  const sessions = new Map<string, SessionState>()
  const lastPush = new Map<string, number>()
  const pending = new Map<string, ReturnType<typeof setTimeout>>()

  const push = (sessionID: string) => {
    void (async () => {
      const s = sessions.get(sessionID)
      if (!s) return
      const target = settings.url.replace(/\/+$/, "") + (settings.path.startsWith("/") ? settings.path : `/${settings.path}`)
      const status = s.status ?? "idle"
      const payload = {
        source: "opencode",
        kind: "ai-face",
        ts: Date.now(),
        project: { name: projectName, emoji },
        session: { id: sessionID, title: s.title ?? "", status },
        agent: { name: s.agent ?? "build", model: s.model ?? "", provider: s.provider ?? "" },
        task: {
          text: s.task ?? "",
          partType: s.partType ?? "",
          partState: s.partState ?? "",
          step: s.step ?? 0,
        },
        display: `${emoji ? `${emoji} ` : ""}${s.title || sessionID} · ${status}${s.agent ? ` · ${s.agent}` : ""}${
          s.model ? ` · ${s.model}` : ""
        }`,
      }
      try {
        await fetch(target, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        })
      } catch {
      }
    })()
  }

  const schedule = (sessionID: string) => {
    const now = Date.now()
    const last = lastPush.get(sessionID) ?? 0
    const wait = Math.max(0, settings.minInterval - (now - last))
    if (wait === 0) {
      lastPush.set(sessionID, now)
      push(sessionID)
      return
    }
    const existing = pending.get(sessionID)
    if (existing) clearTimeout(existing)
    pending.set(
      sessionID,
      setTimeout(() => {
        lastPush.set(sessionID, Date.now())
        pending.delete(sessionID)
        push(sessionID)
      }, wait),
    )
  }

  const state = (sessionID: string) => {
    let s = sessions.get(sessionID)
    if (!s) {
      s = { step: 0 }
      sessions.set(sessionID, s)
    }
    return s
  }

  return {
    config: (cfg: any) => {
      const a = cfg?.astrolabe ?? {}
      settings.enabled = a.enabled === true
      if (typeof a.url === "string" && a.url.length > 0) settings.url = a.url
      if (typeof a.path === "string" && a.path.length > 0) settings.path = a.path
      if (typeof a.min_interval === "number") settings.minInterval = a.min_interval
      if (typeof cfg?.emoji === "string") emoji = cfg.emoji
    },
    async event({ event }: any) {
      if (!settings.enabled) return
      const d = event?.properties ?? {}
      const sessionID = d.sessionID
      if (!sessionID) return
      const s = state(sessionID)

      if (event.type === "session.updated") {
        if (typeof d.info?.title === "string") s.title = d.info.title
        if (typeof d.info?.agent === "string") s.agent = d.info.agent
        if (typeof d.info?.model === "string") s.model = d.info.model
        schedule(sessionID)
        return
      }

      if (event.type === "session.status") {
        s.status = d.status?.type
        schedule(sessionID)
        return
      }

      if (event.type === "message.updated") {
        const info = d.info ?? {}
        if (typeof info.agent === "string") s.agent = info.agent
        if (typeof info.modelID === "string") s.model = info.modelID
        if (typeof info.providerID === "string") s.provider = info.providerID
        if (info.role === "user" && typeof d.part?.text === "string" && d.part.text.trim()) {
          s.task = d.part.text.trim().slice(0, 300)
        }
        schedule(sessionID)
        return
      }

      if (event.type === "message.part.updated") {
        const part = d.part ?? {}
        if (typeof part.type === "string") s.partType = part.type
        if (typeof part.state === "string") s.partState = part.state
        if (part.type === "step-finish") s.step += 1
        schedule(sessionID)
      }
    },
  }
}) satisfies Plugin
