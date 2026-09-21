# Agent instructions

Helsinki metropolitan apartment-location explorer: a free, **static** public website (GitHub Pages) that scores residential buildings against user preferences. All GIS work runs offline in a local Python pipeline (GeoPandas/Shapely, Parquet, Pytest); the web app (React, TypeScript, Vite, MapLibre) loads pre-computed static artifacts. `SPEC.md` is the full contract.

## Source of truth

- Read `SPEC.md` before working; it is the normative product and technical contract.
- Do not repeat the completed interview or research, or reopen settled decisions, unless implementation reveals a concrete contradiction or invalid source assumption.

## Workflow

- Read existing code and tests before changing them.
- Keep changes small and focused. If a task will touch more than five files, first propose staged slices and the exact files in the next slice; wait for approval before editing.
- Add tests for new behavior. For a bug, reproduce it with a failing test before fixing it.
- Run relevant tests before reporting completion and before any requested commit. If tests fail after a change, stop and report the failure instead of layering unrelated fixes.
- Do not commit, push, deploy, publish data, or write to external services unless explicitly asked.

## Approval required

Ask before:

- adding or installing a dependency; explain why it is needed and the maintained alternative considered;
- changing a public interface, exported schema, persisted preference format, or `SPEC.md`;
- modifying repository-root `config/` or `infrastructure/`;
- deleting or renaming files;
- introducing authentication, payments, personal data, a paid source, or a source with unclear reuse rights.

## Project rules (non-obvious)

- **Static only.** No runtime server, database, GIS service, secret, or required third-party API. All downloads, GIS intersections, and routing happen offline in the pipeline; the frontend never recomputes GIS.
- **Unknown is data.** Never convert missing or partial evidence to zero, failure, or a fabricated value. Preferences never overwrite raw source values.
- **Only free, redistributable sources will be published online.** No paid licences or data-opening requests. Never republish online any source without proven republish rights.
- **Helsinki area rentals are local-only.** `data/aluevuokraus_alue.geojson` and every extraction or derivative from it may be used only on this machine; never add them to a public release, web artifact, or published source manifest. Permit geometry is positive local evidence of Helsinki city ownership for the covered area, but not evidence of a building's plot tenure.
- **Config lives in `pipeline/config`.** Do not edit repo-root `/config` or `/infrastructure`.
- **Language split.** Finnish user-facing text; English technical identifiers in code and data schemas.

## Communication

- Be direct. State uncertainty instead of guessing.
- Ask only when a missing decision materially changes the result or safety.
- Report changed files, exact checks run and their results, and remaining work.

## Skills

- Use `spec-first-feature` to execute `SPEC.md` in small verified slices without repeating the completed interview.
- Use `keep-it-small` for implementation scope control.
- Use `regression-guard` for bugs and regressions.
- Use `code-review` in a fresh context before release.

## Commands

No build or test commands exist yet. Do not invent them. The first scaffolding slice must document verified commands in `README.md` and replace this paragraph with those commands.
