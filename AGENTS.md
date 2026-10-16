# Project instructions

- Keep agent plans, checklists, handoffs, and audits together in the user-selected task folder under `.plans/agents/`.
- For a new or resumed session, the user can identify an ongoing task by its folder name under `.plans/agents/`. Read its available handoff, plan, checklist, and audit records before continuing. Do not assume another task folder is active.
- Keep `.plans/` Git-visible; do not add ignore or exclude rules for it. Review documents for credentials, personal paths, and private host details before publication.
- Treat `.plans/project-plans/` as the broader project todo list: pending additions belong in `todo/` and completed plans in `completed/`.
- Other existing or future project folders may coexist under `.plans/`; do not treat the project todo list as the active agent task.
- Keep raw browser captures and credentials in the ignored `.tmp/` evidence directory.
- Keep userscript guides in `docs/userscripts/`.
- Maintain GitHub Fluid Width release history only in the collapsible changelog in `docs/userscripts/github-fluid-width.md`; update the userscript's `@version` metadata for releases.
