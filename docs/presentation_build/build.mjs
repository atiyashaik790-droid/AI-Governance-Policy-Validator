import fs from 'node:fs/promises';
import path from 'node:path';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const root = process.cwd();
const output = path.join(root, 'docs/presentation_output/AI_Governance_Policy_Validator_Demo.pptx');
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const colors = { navy: '#0F172A', blue: '#2563EB', violet: '#7C3AED', cyan: '#06B6D4', green: '#10B981', amber: '#F59E0B', white: '#FFFFFF', muted: '#CBD5E1' };

function shape(slide, geometry, left, top, width, height, fill, line = 'none') {
  return slide.shapes.add({ geometry, position: { left, top, width, height }, fill, line: { style: 'solid', fill: line, width: line === 'none' ? 0 : 1 } });
}
function label(slide, value, left, top, width, height, size = 26, color = colors.white, bold = false) {
  const box = shape(slide, 'textbox', left, top, width, height, 'none');
  box.text = value;
  box.text.style = { fontFamily: 'Arial', fontSize: size, color, bold, verticalAlignment: 'middle' };
  return box;
}
function base(title, section) {
  const slide = deck.slides.add();
  slide.background.fill = colors.navy;
  shape(slide, 'rect', 0, 0, 1280, 12, colors.blue);
  label(slide, section.toUpperCase(), 70, 42, 460, 26, 16, colors.cyan, true);
  label(slide, title, 70, 84, 1140, 85, 40, colors.white, true);
  label(slide, `${String(deck.slides.items.length).padStart(2, '0')}  |  AI Governance Policy Validator`, 70, 668, 1100, 24, 13, colors.muted);
  return slide;
}
function rows(slide, items, top = 205) {
  items.forEach((item, index) => {
    const y = top + index * 94;
    shape(slide, 'roundRect', 70, y, 1140, 72, '#1E293B');
    shape(slide, 'rect', 70, y, 8, 72, [colors.blue, colors.violet, colors.cyan, colors.green, colors.amber][index % 5]);
    label(slide, item, 100, y + 12, 1070, 48, 24);
  });
}

let slide = base('Governed AI for enterprise use', 'Project overview');
label(slide, 'A policy engine between employees, applications and language models', 72, 215, 1050, 110, 31, colors.muted);
shape(slide, 'roundRect', 72, 405, 1135, 135, '#1E293B');
label(slide, 'Local candidate validated  •  Azure cutover pending recovery controls', 100, 440, 1080, 75, 27, colors.cyan, true);

slide = base('The problem', 'Business need');
rows(slide, ['Prompts can expose personal data, secrets or confidential terms', 'Generated answers can return unsafe or sensitive content', 'Teams need explainable decisions and an audit trail']);

slide = base('One website, two role-based portals', 'Experience');
rows(slide, ['Admin portal: policies, categories, simulator, reviews and reports', 'Employee portal: governed AI chat with clear decision messages', 'Backend authorization checks every API request and tenant boundary']);

slide = base('Modular monolith on Azure', 'Architecture');
rows(slide, ['React + TypeScript frontend served with FastAPI', 'SQLAlchemy + Azure SQL for policies, sessions and evidence', 'Azure OpenAI, OpenAI Moderation and ADLS Gen2 integrations', 'Microsoft Entra ID for SSO and backend-managed sessions'], 190);

slide = base('Every active policy is evaluated', 'Governance flow');
rows(slide, ['Capture published policy versions for the tenant', 'Inspect input, redact when permitted, then reinspect', 'Withhold blocked or held prompts from the model', 'Inspect generated output before returning it to the employee'], 190);

slide = base('Decisions have explicit precedence', 'Policy engine');
rows(slide, ['BLOCK overrides every permissive match', 'HUMAN_REVIEW holds content unless a blocking rule also matches', 'REDACT releases only content that passes reinspection', 'ALLOW applies only when every required control succeeds'], 190);

slide = base('Policies and categories are data', 'Administration');
rows(slide, ['Multiple published policies can run at once', 'Custom categories reuse supported keyword and regex detectors', 'Version history and audit events attribute each change', 'Eight examples seed the demo; the engine has no eight-policy limit'], 190);

slide = base('Sensitive review content stays protected', 'Human Review');
rows(slide, ['Authenticated encryption protects held text at rest', 'Authorized reveal attempts are audited and tenant-scoped', 'Approval does not silently send the held prompt to Azure OpenAI', 'Protected content has a seven-day retention target'], 190);

slide = base('What the dashboards show', 'Analytics');
rows(slide, ['Execution counts by decision and recent activity', 'Policy and category attribution for explainable findings', 'Compliance scoring weights: secrets 30, PII 25, moderation 25, rules 20', 'Reports export sanitized evidence to ADLS Gen2'], 190);

slide = base('Local validation and current boundary', 'Results');
rows(slide, ['Backend regression: 1,325 tests passed', 'Frontend regression: 133 passed, 1 skipped; production build passed', 'Fresh Azure database revision 008 has eight seeded policies', 'Hosted candidate cutover and end-to-end acceptance remain pending'], 190);

slide = base('Live demo sequence', 'Presenter guide');
rows(slide, ['Sign in and show role-specific navigation', 'Create a category and policy, then simulate a blocked keyword', 'Show redaction, review queue and execution attribution', 'Open analytics and explain the current deployment boundary'], 190);

slide = base('Lessons and next gates', 'Close');
rows(slide, ['Versioned policy snapshots make decisions reproducible', 'Fail-closed behavior protects provider calls and output release', 'Recovery proof and safe settings restoration gate cutover', 'After approval: deploy the pinned candidate and run hosted acceptance'], 190);

await fs.mkdir(path.dirname(output), { recursive: true });
await (await PresentationFile.exportPptx(deck)).save(output);
console.log(output);
