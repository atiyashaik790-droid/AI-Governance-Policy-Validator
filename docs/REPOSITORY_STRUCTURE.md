# Repository structure

```text
.github/workflows/     Continuous integration
backend/
  app/                 FastAPI application and domain modules
  migrations/          Alembic environment and versioned migrations
  tests/               Backend regression tests
  Dockerfile           Backend container build
  alembic.ini          Migration configuration
  pyproject.toml       Python test and lint configuration
  requirements*.txt    Dependencies and locked versions
frontend/
  src/                 React application and existing frontend tests
  Dockerfile           Frontend container build
  package*.json        npm scripts, dependencies, and lockfile
  vite.config.ts       Development, build, and test configuration
  tsconfig.json        TypeScript configuration
scripts/               Provisioning, diagnostics, demos, deployment packaging
deployment/           Hosting startup, example settings, review-only SQL
docs/
  guides/              Setup and explanatory guides
  runbooks/            Operational procedures
  reports/             Acceptance and historical reports, production backlog
  evidence/            Original dated evidence and manifests
  sql/                 SQL review and verification resources
  *.json               Existing script result destinations
  API.md               API reference
  ARCHITECTURE.md       Application architecture
  README.md            Documentation index
.env.example           Committable environment template
.gitignore             Local data and secret exclusions
docker-compose.yml     Existing local container orchestration
README.md              Project entry point
```

## Path compatibility

The runtime folders remain at their existing locations. Python imports use `backend/app`, migrations use `backend/migrations`, and standalone scripts derive the repository root from their own location. The frontend integration test, deployment packager, Docker build contexts, CI, and environment resolution also rely on the current paths.

Keep application source, test files, entry points, lockfiles, and runtime configuration in place unless a future code refactor explicitly updates and verifies their consumers. Documentation is grouped by purpose; links point to its new locations.

## Local files

`.env`, `.demo-tokens.json`, `.azure-sql-cli/`, `.venv/`, database files, `node_modules/`, `dist/`, caches, and `artifacts/` are local state or generated output excluded by the existing `.gitignore`. They are deliberately preserved. Do not move a live database, credentials, or environment files as part of a cosmetic repository cleanup.

This layout supports maintenance and deployment packaging. Production readiness still depends on the controls and limitations recorded in the [production backlog](reports/PRODUCTION_BACKLOG.md); folder organization does not change application capabilities.
