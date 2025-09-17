// web/next/pages/items.tsx
import { useEffect, useMemo, useState } from "react"

type Row = { id?: number; name?: string; description?: string }

const PAGE_SIZE = 10

export default function Items() {
  const role = "admin" // מדגים RBAC בסיסי; בהמשך נקרא מ-querystring
  const [name, setName] = useState("")
  const [desc, setDesc] = useState("")
  const [rows, setRows] = useState<Row[]>([])
  const [q, setQ] = useState("")
  const [page, setPage] = useState(1)
  const [demo, setDemo] = useState<any>(null)
  const [toast, setToast] = useState<{ type: "ok" | "err"; text: string } | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)

  async function load() {
    const r = await fetch("/api/items")
    if (r.ok) setRows(await r.json())
  }

  async function create() {
    if (!name.trim()) return setToast({ type: "err", text: "שם נדרש" })
    const r = await fetch("/api/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: desc }),
    })
    if (r.ok) {
      setName("")
      setDesc("")
      await load()
      setToast({ type: "ok", text: "נשמר" })
    } else {
      setToast({ type: "err", text: "שמירה נכשלה" })
    }
  }

  async function update(id: number, patch: Partial<Row>) {
    const r = await fetch(`/api/items/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    })
    if (r.ok) {
      await load()
      setToast({ type: "ok", text: "עודכן" })
    } else setToast({ type: "err", text: "עדכון נכשל" })
  }

  async function remove(id: number) {
    const r = await fetch(`/api/items/${id}`, { method: "DELETE" })
    if (r.ok) {
      setConfirmId(null)
      await load()
      setToast({ type: "ok", text: "נמחק" })
    } else setToast({ type: "err", text: "מחיקה נכשלה" })
  }

  async function runDemo() {
    const src = "Items are records with name and description, saved via /api/items."
    const url = `/grounded/demo?q=${encodeURIComponent("Summarize items")}&src_text=${encodeURIComponent(src)}`
    const r = await fetch(url)
    if (r.ok) setDemo(await r.json())
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(
    () =>
      rows.filter((r) =>
        (r.name || "").toLowerCase().includes(q.toLowerCase()) ||
        (r.description || "").toLowerCase().includes(q.toLowerCase())
      ),
    [rows, q]
  )
  const maxPage = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <main className="mx-auto max-w-5xl p-6 font-[system-ui]">
      <h1 className="text-3xl font-bold mb-4">Items</h1>
      <div className="text-sm text-gray-500 mb-6">role: {role}</div>

      {/* Form */}
      <section className="mb-8">
        <h2 className="font-bold mb-2">טופס</h2>
        <div className="space-y-2">
          <input value={name} onChange={e => setName(e.target.value)} placeholder="name"
            className="w-full border rounded px-3 py-2" />
          <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="description"
            className="w-full border rounded px-3 py-2" />
          <button onClick={create}
            className="rounded bg-blue-600 text-white px-4 py-2 hover:bg-blue-700">שמור</button>
        </div>
      </section>

      {/* Table */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-bold">רשימה</h2>
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="חיפוש…"
            className="border rounded px-3 py-1 text-sm" />
        </div>

        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="border px-2 py-2 w-12">#</th>
              <th className="border px-2 py-2">Name</th>
              <th className="border px-2 py-2">Description</th>
              <th className="border px-2 py-2 w-48">Actions</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r, i) => (
              <tr key={r.id ?? i}>
                <td className="border px-2 py-1">{r.id ?? "–"}</td>
                <td className="border px-2 py-1">{r.name}</td>
                <td className="border px-2 py-1">{r.description}</td>
                <td className="border px-2 py-1">
                  <div className="flex gap-2">
                    <button className="rounded border px-2 py-1 hover:bg-gray-50"
                      onClick={() => update(Number(r.id), { name: (r.name || "") + " ✓✓" })}>ערוך</button>
                    <button className="rounded border px-2 py-1 text-red-600 hover:bg-red-50"
                      onClick={() => setConfirmId(Number(r.id))}>מחק</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="flex items-center gap-3 mt-3 text-sm">
          <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}
            className="border rounded px-2 py-1 disabled:opacity-40">קודם</button>
          <span>{page} / {maxPage}</span>
          <button disabled={page >= maxPage} onClick={() => setPage(p => Math.min(maxPage, p + 1))}
            className="border rounded px-2 py-1 disabled:opacity-40">הבא</button>

          <button onClick={runDemo} className="ml-auto border rounded px-3 py-1">Grounded demo</button>
        </div>
      </section>

      {/* Demo result */}
      {demo && (
        <section className="mt-6 border rounded p-3 text-sm">
          <div><b>Answer:</b> {demo.answer}</div>
          <div className="mt-1 grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div>coverage: {(demo.coverage * 100).toFixed(1)}%</div>
            <div>provider: {demo.provider}</div>
            <div>latency: {demo.latency_ms} ms</div>
            <div>cost: ${demo.cost_usd}</div>
          </div>
          {Array.isArray(demo.per_claim) && demo.per_claim.length > 0 && (
            <ul className="mt-2 list-disc ps-5">
              {demo.per_claim.map((c: any, i: number) => (
                <li key={i}>{c.claim} — source: {c.source_id || "n/a"}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Confirm dialog */}
      {confirmId && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center">
          <div className="bg-white rounded shadow p-4 w-80">
            <h3 className="font-bold mb-2">לאשר מחיקה?</h3>
            <p className="text-sm text-gray-600 mb-4">אי אפשר לבטל פעולה זו.</p>
            <div className="flex gap-2">
              <button onClick={() => setConfirmId(null)} className="border rounded px-3 py-1">ביטול</button>
              <button onClick={() => remove(confirmId)} className="ml-auto bg-red-600 text-white rounded px-3 py-1 hover:bg-red-700">
                מחק
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 rounded px-3 py-2 text-white ${toast.type === "ok" ? "bg-emerald-600" : "bg-red-600"}`}>
          {toast.text}
          <button className="ml-3 text-white/80" onClick={() => setToast(null)}>×</button>
        </div>
      )}
    </main>
  )
}
