/**
 * Exports the upstream props tables to JSON for the Qt showcase.
 *
 * Reads every `apps/site/src/props/*.ts` in ~/dev/sg-widgets, resolves each item's
 * `extends` chain with the upstream's own `_resolve.ts`, and writes one
 * `docs/widgets/<name>.props.json` here per item, plus `docs/widgets/_index.json`
 * holding the sidebar read out of `apps/site/astro.config.mjs`.
 *
 * Two renames are applied: a prop name becomes snake_case and an event name becomes
 * a Qt signal name. Every other field is copied verbatim; `tools/props_types.py` is
 * the pass that adds a Python type.
 *
 *     cd ~/dev/sg-widgets && node ~/dev/sg-widgets-qt/tools/export_props.mjs
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { register } from 'node:module';
import { homedir } from 'node:os';
import { dirname, join, resolve as resolvePath } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolvePath(HERE, '..');
const OUT = join(REPO, 'docs', 'widgets');

/** The upstream checkout: an override, the directory the script was run from, or the default. */
function upstreamRoot() {
  const candidates = [process.env.SG_WIDGETS, process.cwd(), join(homedir(), 'dev', 'sg-widgets')];
  for (const candidate of candidates) {
    if (candidate && existsSync(join(candidate, 'apps/site/src/props/_resolve.ts'))) return candidate;
  }
  throw new Error('No sg-widgets checkout found. Run from it, or set SG_WIDGETS.');
}

const UPSTREAM = upstreamRoot();
const PROPS_DIR = join(UPSTREAM, 'apps/site/src/props');
const ASTRO_CONFIG = join(UPSTREAM, 'apps/site/astro.config.mjs');
const DOCS_DIR = join(UPSTREAM, 'apps/site/src/content/docs');

// `_resolve.ts` collects the props files with `import.meta.glob`, which is Vite's and not
// Node's. The loader hook points that one call at a map this script builds itself, so the
// upstream file runs unedited and its resolution of `extends` is the one used here.
const hook = `
export async function load(url, context, nextLoad) {
  const loaded = await nextLoad(url, context);
  if (!url.endsWith('/_resolve.ts')) return loaded;
  const source =
    typeof loaded.source === 'string' ? loaded.source : new TextDecoder().decode(loaded.source);
  return { ...loaded, source: source.replace(/import\\.meta\\.glob/g, 'globalThis.__sgGlob') };
}
`;
register(`data:text/javascript,${encodeURIComponent(hook)}`);

const itemNames = readdirSync(PROPS_DIR)
  .filter((file) => file.endsWith('.ts') && !file.startsWith('_'))
  .map((file) => file.slice(0, -3))
  .sort();

const modules = {};
for (const name of itemNames) {
  modules[`./${name}.ts`] = await import(pathToFileURL(join(PROPS_DIR, `${name}.ts`)).href);
}
globalThis.__sgGlob = () => modules;

const { fileOf, pageOf, resolve } = await import(pathToFileURL(join(PROPS_DIR, '_resolve.ts')).href);

/** `labelField` -> `label_field`. A two-spelling name keeps both spellings. */
function snakeCase(name) {
  return name
    .split('/')
    .map((part) =>
      part
        .trim()
        .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
        .replace(/([A-Z]+)([A-Z][a-z])/g, '$1_$2')
        .replace(/[-\s]+/g, '_')
        .toLowerCase(),
    )
    .join(' / ');
}

/** `onValueChange` -> `value_changed`, `onOpenChange` -> `open_changed`, `onError` -> `error`. */
function signalName(name) {
  const bare = name.replace(/^on/, '');
  if (bare === 'Change') return 'changed';
  if (bare.endsWith('Change')) return `${snakeCase(bare.slice(0, -'Change'.length))}_changed`;
  // A verb is a Qt signal in the past tense; a noun (`onError`) stays as it is.
  const verbs = { Click: 'clicked', Select: 'selected', Remove: 'removed', Pick: 'picked', Open: 'opened', Close: 'closed', Submit: 'submitted', Load: 'loaded', LoadMore: 'load_more_requested', Commit: 'committed', Cancel: 'cancelled', Clear: 'cleared', Activate: 'activated', Toggle: 'toggled', Reorder: 'reordered', Expand: 'expanded', Collapse: 'collapsed', Focus: 'focused', Blur: 'blurred' };
  if (verbs[bare]) return verbs[bare];
  return snakeCase(bare);
}

/** The `class` prop becomes nothing here: a caller styles through the theme. */
function isClassRow(name) {
  return snakeCase(name)
    .split(' / ')
    .every((part) => part === 'class' || part === 'class_name');
}

/** One resolved entry as a JSON row: the upstream fields, the rename, and who declares it. */
function rowOf(entry, kind, item) {
  const { only, ...row } = entry.row;
  if (only === 'svelte') return null;
  if (kind === 'props') {
    if (isClassRow(row.name)) return null;
    row.name = snakeCase(row.name);
  }
  if (kind === 'events') row.name = signalName(row.name);
  if (entry.owner !== item) row.owner = entry.owner;
  return row;
}

function rowsOf(item, kind) {
  return resolve(item, kind)
    .map((entry) => rowOf(entry, kind, item))
    .filter(Boolean);
}

mkdirSync(OUT, { recursive: true });

let written = 0;
for (const name of itemNames) {
  const file = fileOf(name);
  const table = {
    name,
    page: pageOf(name),
    declares: file.declares === undefined ? null : file.declares,
    props: rowsOf(name, 'props'),
    events: rowsOf(name, 'events'),
    slots: rowsOf(name, 'slots'),
    keyboard: rowsOf(name, 'keyboard'),
  };
  writeFileSync(join(OUT, `${name}.props.json`), `${JSON.stringify(table, null, 2)}\n`);
  written += 1;
}

// The sidebar. Read out of the Astro config as text: the config imports the Astro
// integrations, which are not this script's to load.
const config = readFileSync(ASTRO_CONFIG, 'utf8');

function sidebarSlice() {
  const start = config.indexOf('sidebar: [');
  if (start < 0) throw new Error('No sidebar in astro.config.mjs');
  let depth = 0;
  for (let i = config.indexOf('[', start); i < config.length; i += 1) {
    if (config[i] === '[') depth += 1;
    else if (config[i] === ']') {
      depth -= 1;
      if (depth === 0) return config.slice(start, i + 1);
    }
  }
  throw new Error('Unterminated sidebar in astro.config.mjs');
}

const sidebar = sidebarSlice();

/** The names of a `['a', 'b'].map((n) => ({ slug: `widgets/${n}` }))` category. */
const widgetCategories = [
  ...sidebar.matchAll(/label: '([^']+)',\s*items: \[((?:\s*'[^']+'\s*,?)+)\]\.map\(/g),
].map(([, category, list]) => ({
  category,
  items: [...list.matchAll(/'([^']+)'/g)].map(([, item]) => item),
}));

function slugsUnder(label, prefix) {
  const group = sidebar.slice(sidebar.indexOf(`label: '${label}'`));
  const end = group.indexOf('},\n        {');
  return [...group.slice(0, end < 0 ? undefined : end).matchAll(/slug: '([^']+)'/g)]
    .map(([, slug]) => slug)
    .filter((slug) => slug.startsWith(prefix))
    .map((slug) => slug.slice(prefix.length));
}

/** A group Starlight fills from a directory is filled from the same directory here. */
function autogenerated(directory) {
  if (!sidebar.includes(`directory: '${directory}'`)) return [];
  const pages = readdirSync(join(DOCS_DIR, directory))
    .filter((file) => file.endsWith('.mdx'))
    .map((file) => file.slice(0, -4))
    .sort();
  return ['index', ...pages.filter((page) => page !== 'index')];
}

const index = {
  start: slugsUnder('Start', 'start/'),
  core: autogenerated('core'),
  overview: sidebar.includes("slug: 'widgets'") ? 'index' : null,
  widgets: widgetCategories,
};
writeFileSync(join(OUT, '_index.json'), `${JSON.stringify(index, null, 2)}\n`);

const listed = new Set(widgetCategories.flatMap((group) => group.items));
const pages = readdirSync(join(DOCS_DIR, 'widgets'))
  .filter((file) => file.endsWith('.mdx'))
  .map((file) => file.slice(0, -4))
  .filter((page) => page !== 'index' && !listed.has(page));

console.log(`${written} props files -> docs/widgets/*.props.json`);
console.log(`sidebar -> docs/widgets/_index.json (${widgetCategories.length} categories)`);
if (pages.length) console.log(`pages outside the sidebar: ${pages.join(', ')}`);
