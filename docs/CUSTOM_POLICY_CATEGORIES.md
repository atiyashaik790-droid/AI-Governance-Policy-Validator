# Custom policy categories

## Standalone catalog (revision 009)

The Admin portal now has a Category Management page backed by `governance_categories` and the many-to-many `policy_categories` table. Migration 009 seeds eight protected built-in category records. Admins can create custom keyword or safe-regex categories, search and filter the catalog, view associations, assign categories to draft policies, and remove eligible categories. The backend enforces tenant scope, role checks, optimistic revision checks for edits and deletion, and audit events. A custom category's supported detector configuration is copied into the assigned policy draft; it takes effect only after the normal policy publication and activation workflow. A category assigned to a published policy cannot be edited or removed until the policy lifecycle permits association changes. Built-in associations organize policies but do not create a new detector.

The catalog is synchronized with the older embedded custom-category editor. Migration 009 backfills existing draft custom categories into tenant-scoped catalog records and associations, changes their draft IDs to deterministic tenant-scoped IDs, and increments the policy row version so stale editors must reload. Existing published policy snapshots remain immutable. Conflicting definitions for the same tenant/category ID stop the migration for operator review rather than choosing a rule silently. Azure SQL migration 009 and exact runtime grants are prepared locally but have not been applied to the hosted database.

Admins can add, edit, disable and remove categories in the policy draft editor.
Each category has a stable ID, name, description, action, detection method and
patterns. Policy Owners can edit other draft fields while preserving existing
custom categories; changing categories through create, update or rollback
requires Admin. Existing tenant, session, CSRF and publication controls apply.
Published JSON snapshots remain immutable; existing documents without categories
continue to work. Catalog management requires migration 009.

Keyword/phrase and regex matching are case insensitive. Categories enforce
BLOCK, REDACT or HUMAN_REVIEW in LEGACY, MULTI and existing draft simulation.
Redactions pass the existing reinspection gates. Audit findings contain stable
category IDs, counts and actions rather than matched content or pattern text.
Missing custom inspection evidence and detector failures block release.

Limits: 20 categories per policy, 10 patterns per category, 200 characters per
pattern and 12,000 inspected characters. Regex supports literals, character
classes, anchors and quantifiers; groups, alternatives and backreferences are
rejected, and explicit repetition counts cannot exceed 1000. Empty-text matches
are rejected at validation; zero-width runtime matches block inspection.
Each category has a 50 ms matching budget within the existing detector capacity
and governance deadline bounds. Timeout means UNKNOWN/BLOCK, never an implicit
pass. Longer generated output therefore fails closed when custom rules apply.
The explicitly declared regex dependency is already present in the lock file.

LEGACY explanatory scores retain built-in weights and assign each custom
category weight 20. Scores never override enforcement decisions. MULTI retains
per-policy evidence without inventing an aggregate score.
