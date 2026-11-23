# Mind Map Monkey

A mind-map editor that keeps your maps as plain [Mermaid](https://mermaid.js.org/syntax/mindmap.html) `.mmd` files in OneDrive. Build a map with the mouse, keyboard or touch, then open the same file in any Mermaid-aware tool.

- Add, rearrange and collapse branches, add descriptions with basic formatting, tags, importance and cross-links.
- Open, save and auto-save to OneDrive, with a short save lock and a merge prompt when someone else changed the file.
- Find nodes, undo and redo, full screen, and a pinned or floating details panel.
- Export Mermaid code or a PNG; import a Mermaid file or pasted code.
- Works on phones, with a compact toolbar and a bottom edit sheet.

Keyboard shortcuts: `Ctrl/⌘+S` save, `Ctrl/⌘+F` find, `Ctrl/⌘+Shift+F` full screen, `Ctrl/⌘+Z` undo, `Ctrl/⌘+Y` redo. The built-in help map (**File → Open help map**) covers the rest.

See [KNOWN-ISSUES.md](./KNOWN-ISSUES.md) for current limitations.

## Template

The app was built from the App Builder template: React + TypeScript + Vite with **shadcn/ui (new-york, Radix)** + **Tailwind CSS v4** and a small, familiar set of libraries.

## Stack

- **React 19** + **TypeScript** + **Vite 7** (run with **bun**)
- **shadcn/ui** (`new-york`) on **Radix** primitives (the unified `radix-ui` package)
- **Tailwind CSS v4** (CSS-first, no JS config — tokens live in `src/index.css`)
- **react-router-dom 7** for routing
- **TanStack Query 5** for async data, **TanStack Table 8** for grids
- **zustand** for global state (only when needed; `useState` for local)
- **recharts** for charts, **@dnd-kit** for drag & drop, **lucide-react** for icons, **sonner** for toasts
- **html2canvas-pro 2.4.2 + jsPDF 4.2.1** for bounded Canvas-style PDF capture of an app-owned screen or container, including modern CSS colors and a small backdrop bleed that preserves rounded edges and shadows (`unpdf` remains the existing-PDF extraction tool); the shared button bounds connector-neutral follow-up callbacks so a stalled save cannot wedge export
- **@microsoft/managed-apps** — the connector runtime for an app that carries a
  data-source binding (Dataverse, SharePoint, Excel, Office 365, SQL, …)

## Scripts

| Script | What it does |
|--------|--------------|
| `bun run check` | Type-check (`tsc`) + Vite build dry-run + ESLint — the required gate before commit |
| `bun run typecheck` | Type-check only (`tsc -p tsconfig.app.json --noEmit`) — the cheap gate the app-builder agent runs before hand-back |
| `bun run lint` | ESLint only |
| `bun run dev` | Vite dev server (managed externally by the runtime — do not run by hand) |
| `bun run build` | Production build (`vite build`) — no type-check |
| `bun run preview` | Preview a production build |

## Local mode (without the host)

To test the app in an ordinary browser tab, outside the Copilot Managed Runtime player, start the dev server (`ms app dev` or `bun run dev`) and open:

```
http://localhost:5173/?standalone
```

Everything except OneDrive works: editing, layout, find, undo, import and export of Mermaid and PNG, and the phone layout. OneDrive actions (open, save, refresh, the save lock) fail straight away with a "OneDrive isn't connected in local mode" message, and the footer shows **Local mode: OneDrive is off**. The setting lasts for the browser tab; open `?standalone=0` to turn it off. Local mode only exists in the dev build on `localhost`, so a deployed app never enters it.

## Project layout

```
src/
  App.tsx        routes + providers
  main.tsx       entry point
  index.css      Tailwind + design tokens (oklch)
  routes.tsx     route + nav manifest (add a page here)
  components/    app-shell, PDF target export button, error-boundary, confirm-dialog, states, page-section + ui/ (shadcn, pre-installed)
  hooks/         reusable hooks (use-mobile, use-confirm)
  lib/           cn(), query-client, PDF Blob helper, store (zustand), safe-url, console capture, Cowork parent transport
  pages/         route-level screens (home, not-found)
  types/         fixed parent-frame message contract
generated/       typed connector client, present only when the app carries a binding (do not edit)
```

Path alias: `@/` → `src/`.

## Agent instructions

The build/iterate rules an agent needs at the per-app level — stack conventions, the Tailwind v4
cheat-sheet, structure, and the on-demand feature sections — live in **[AGENTS.md](./AGENTS.md)**, with the
OKLCH presets in its sibling **[THEMING.md](./THEMING.md)** (read on a turn-1 build or recolor/restyle). The file
format is agent-agnostic — any coding agent (Claude Code, Codex, Cursor, …) reads these, and there is
intentionally no `CLAUDE.md`. Within the App Builder, the subagent that builds and iterates apps is
additionally governed by its own always-loaded operating rules — the verification loop and the full "what
not to touch" ban list — which are enforced there and deliberately **not** duplicated into this `AGENTS.md`
(so this per-app file is intentionally not a self-sufficient contract for an external agent running outside
the harness).

## Your own managed app

The GitHub repository does not include `ms.config.json` or local app metadata.
These contain identifiers and connection references specific to an individual
app and environment. They are ignored by Git.

To create your own development app, install Node.js 24.11 or later, Git, and
the [Copilot Managed Runtime CLI](https://www.npmjs.com/package/@microsoft/cmr-cli),
then clone this repository and run:

```sh
npm ci
ms auth login
ms app init --display-name "Mind Map Monkey" --repo none
ms app add data-source --connector onedriveforbusiness --as action
ms app dev
```

Sign in and select a suitable environment and OneDrive for Business connection
when prompted. Initialization creates a new, local `ms.config.json`; adding the
data source creates the app's own connection reference and regenerates the
typed client in `generated/`. The `--repo none` option keeps the GitHub remote
unchanged and uses the CLI's artifact-based deployment flow. Deploying is a
separate step. Review regenerated files and other changes for identifiers or
credentials before committing them.

The existing CMR checkout has a separate Git history. Do not merge it into this
repository: its history contains app-specific identifiers. To publish changes
from that checkout, copy the intended source changes into a GitHub checkout,
review them, and make a new GitHub commit.

## Notes

- An unsaved draft and your preferences are kept in the browser's `localStorage`, so a refresh doesn't lose them (see KNOWN-ISSUES for what that means on shared computers).
- `node_modules/` is baked into the orchestrator image and bind-mounted read-only; dependencies are not
  installed or patched per session.
