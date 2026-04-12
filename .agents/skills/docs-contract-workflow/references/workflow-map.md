# Docs Contract Workflow Map

Use this note when you need the deterministic wrapper behavior without rereading
the Python source.

## Exact workflows

- `schema-drift`
  - Writes a findings report under `docs/reports/progress/`
  - May write a proposed contract artifact under `tools/contracts/docs/proposed/`
- `blueprint-lifecycle`
  - Writes a findings report under `docs/reports/progress/`
  - Writes a proposal artifact under `tools/contracts/docs/proposed/`
- `legacy-blueprint-classification`
  - Writes a findings report under `docs/reports/progress/`
  - Writes a proposal artifact under `tools/contracts/docs/proposed/`
- `docs-family`
  - Writes a findings report under `docs/reports/progress/`
  - Writes a proposal artifact under `tools/contracts/docs/proposed/`
- `repo-doc-boundary`
  - Writes a findings report under `docs/reports/progress/`
  - Reads the approved repo/local boundary contract from `tools/contracts/docs/current/`
- `doc-change-propagation`
  - Writes a findings report under `docs/reports/progress/`
  - Reads the approved change-propagation contract from `tools/contracts/docs/current/`
- `relationship-reciprocity`
  - Writes a findings report under `docs/reports/progress/`
  - Reads the approved reciprocity contract from `tools/contracts/docs/current/`
- `generated-report-authority`
  - Writes a findings report under `docs/reports/progress/`
  - Reads the approved generated-report authority contract from `tools/contracts/docs/current/`
- `minimum-linkage`
  - Writes a findings report under `docs/reports/progress/`
  - Reads the approved minimum-linkage contract from `tools/contracts/docs/current/`
- `blueprint-custodian`
  - Writes a progress report under `docs/reports/progress/`
  - May update blueprint frontmatter in `docs/`
- `docs-custodian`
  - Writes a progress report under `docs/reports/progress/`
  - May update non-blueprint docs frontmatter in `docs/`

## Guardrails

- Interpreter workflows are proposal/report producers.
- Custodian workflows are the only mutating workflows.
- Custodians must respect `tools/contracts/docs/README.md`:
  - read only from `current/`
  - refuse mutation when newer related proposals exist in `proposed/`
- If the wrapper reports `blocked`, stop there. Do not hand-roll the mutation.

## Default command

```powershell
python C:\Users\olefa\dev\pete-workspace\tools\scripts\run_docs_contract_workflow.py --workflow <workflow-name>
```
