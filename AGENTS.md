# Project instructions

- Keep agent plans, checklists, handoffs, and audits together in the user-selected task folder under `.plans/agents/`.
- When the user explicitly starts a TODO project, create or reuse its matching `.plans/agents/<project_dir>/` before implementation. Expand the approved rough outline into the full overall plan, mirrored acceptance checklist, and resumable handoff there; keep audits and review notes alongside them as needed. Use `PLAN.md`, `PLAN_checklist.md`, and `PLAN_handoff.md` for new records, preserving established filenames and accepted requirements when resuming.
- Link the TODO entry and rough project outline to that active folder. Keep the full execution plan, checklist, handoff, and audits authoritative there instead of maintaining competing full plans in the TODO area. Saving or publishing an outline does not start implementation.
- For a new or resumed session, the user can identify an ongoing task by its folder name under `.plans/agents/`. Read its available handoff, plan, checklist, and audit records before continuing. Do not assume another task folder is active.
- Keep `.plans/` Git-visible; do not add ignore or exclude rules for it. Review documents for credentials, personal paths, and private host details before publication.
- Treat `.plans/project-plans/` and their `TODO.md` entries as the broader project list of rough outlines: pending additions belong in `todo/` and completed plans in `completed/`. Once a project starts, its full execution records belong under `.plans/agents/<project_dir>/`.
- Other existing or future project folders may coexist under `.plans/`; do not treat the project todo list as the active agent task.
- Keep raw browser captures and credentials in the ignored `.tmp/` evidence directory.
- Group documentation under `docs/shell/`, `docs/python/`, `docs/userscripts/`, `docs/zen-scripts/`, `docs/cheat-sheets/`, and `docs/other/` according to its subject.
- Use dashes instead of spaces in documentation folder names; Markdown filenames may contain spaces.
- Use relative links for repository-owned files and images in documentation. Userscript guides may use hardcoded repository URLs; preserve their intended branch targets.
- Maintain GitHub Fluid Width release history only in the collapsible changelog in `docs/userscripts/github-fluid-width.md`; update the userscript's `@version` metadata for releases.
