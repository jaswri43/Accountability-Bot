import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import type { TaskTemplate, Tier } from "../api/types";
import { DataTable, ErrorBanner, PageHeader, TableMessage, Td, Th, TierTag } from "../components/ui";
import { TIER_LABEL } from "../lib/game";

const FORM_ID = "add-task-template";
const TIERS: Tier[] = ["low", "medium", "high"];

const FIELD =
  "min-h-10 rounded-md border border-line bg-surface px-3 text-sm text-fg placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent";

/** Your task templates (same list as /mytasks), plus an add row at the bottom. */
export function Templates() {
  const [templates, setTemplates] = useState<TaskTemplate[] | null>(null);
  const [description, setDescription] = useState("");
  const [tier, setTier] = useState<Tier>("low");
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api
      .templates()
      .then(setTemplates)
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  }

  useEffect(load, []);

  // Active templates first (in the server's tier order, so numbers run
  // 1..N), then removed ones, which have no number.
  const rows = templates ? [...templates.filter((t) => t.active), ...templates.filter((t) => !t.active)] : null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!description.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.createTemplate(description.trim(), tier);
      // Re-fetch rather than append locally: the new template's position
      // and number depend on the full tier-sorted order (bot/cosmetic.py),
      // which can put it anywhere in the list and shift others -- only the
      // server knows that order.
      load();
      setDescription("");
      setTier("low");
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    setDeletingId(id);
    setError(null);
    try {
      await api.deleteTemplate(id);
      // Same reasoning as create: removing one active template shifts the
      // numbers of every active template after it in tier-sorted order, so
      // a local splice would leave the rest showing stale numbers.
      load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tasks"
        subtitle="Each counted loss draws one of these. Tagging any task Medium or High turns on severity odds."
      />

      {error && <ErrorBanner message={error} />}

      {/* The inputs live in the table's last row; form= ties them to this form. */}
      <form id={FORM_ID} onSubmit={handleSubmit} />

      <DataTable minWidth="36rem">
        <thead>
          <tr>
            <Th className="w-10">#</Th>
            <Th>Description</Th>
            <Th className="w-36">Tier</Th>
            <Th className="w-28">
              <span className="sr-only">Action</span>
            </Th>
          </tr>
        </thead>
        <tbody>
          {rows === null ? (
            <TableMessage colSpan={4}>Loading…</TableMessage>
          ) : rows.length === 0 ? (
            <TableMessage colSpan={4}>
              No tasks yet. Add one below; losses fall back to a generic default until you do.
            </TableMessage>
          ) : (
            rows.map((template) => (
              <tr key={template.id}>
                <Td className="text-muted tabular-nums">{template.number ?? "—"}</Td>
                <Td className={template.active ? "" : "text-muted line-through"}>{template.description}</Td>
                <Td>
                  <TierTag tier={template.tier} />
                </Td>
                <Td align="right">
                  {template.active ? (
                    <button
                      type="button"
                      disabled={deletingId === template.id}
                      onClick={() => handleDelete(template.id)}
                      className="-mx-2 -my-3 inline-flex min-h-11 items-center px-2 text-sm text-muted hover:text-loss disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {deletingId === template.id ? "Removing…" : "Delete"}
                    </button>
                  ) : (
                    <span className="text-xs text-muted">Removed</span>
                  )}
                </Td>
              </tr>
            ))
          )}
        </tbody>
        <tfoot>
          <tr>
            <Td />
            <Td>
              <label htmlFor="description" className="sr-only">
                New task
              </label>
              <input
                id="description"
                form={FORM_ID}
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="New task, e.g. 30 push-ups"
                maxLength={500}
                className={`${FIELD} w-full`}
              />
            </Td>
            <Td>
              <label htmlFor="tier" className="sr-only">
                Tier
              </label>
              <select
                id="tier"
                form={FORM_ID}
                value={tier}
                onChange={(e) => setTier(e.target.value as Tier)}
                className={`${FIELD} w-full`}
              >
                {TIERS.map((t) => (
                  <option key={t} value={t}>
                    {TIER_LABEL[t]}
                  </option>
                ))}
              </select>
            </Td>
            <Td align="right">
              <button
                type="submit"
                form={FORM_ID}
                disabled={submitting || !description.trim()}
                className="min-h-10 rounded-md bg-accent px-4 text-sm font-medium text-on-accent transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "Adding…" : "Add"}
              </button>
            </Td>
          </tr>
        </tfoot>
      </DataTable>
    </div>
  );
}
