# Writing rules

For docs pages, docstrings, comments, STATUS.md, commit messages and PR bodies.

## Documentation

- Written for the person using the widget. It says what the widget does, what it takes, what it
  emits, and how to import it. Nothing about how it was built, tested or mocked.
- Declarative and short. One idea per sentence. No adjectives that sell ("powerful", "beautiful",
  "seamless"). No "simply", "just", "easily".
- Every widget page has, in this order: one sentence saying what it is, the import line, a props
  table (name, type, default, one-line meaning), signals, slots, a keyboard table, and any API
  behaviour the widget relies on with its corpus citation. The showcase draws the tables from the
  `.props.json` beside the page.
- Prose names a file, prop or function only when the reader has to go there. Code goes in a fenced
  block, never inline in a sentence.
- No headers in a page under 300 words. At most three levels anywhere.

## Code comments

Terse and declarative. The code says what it is; comments do not narrate how it got there.

- A docstring is one short sentence saying what the thing does. A parameter gets a phrase only
  when its name does not already say it. Three or four more sentences are the exception, for
  behaviour that is not self-evident.
- Comments appear only where the code alone is hard to follow, and state the rule or the
  constraint, never its discovery.
- No history. No dates, no "used to", no past bugs, no PR or issue numbers, no first person.
- Corpus citations stay (`probe 009`, `field_types/status_list`). They are the only reason this
  repo may claim anything about the API.
- A measured fact the code cannot show survives as one declarative line.
- No em dashes and no en dashes. A full stop, a comma or a colon.

## Commits

One line saying what the change makes true, in the present tense, the way the upstream repo
writes them: "The status picker keeps its highlight across a load-more page". No process narrative.

## Names in examples

Invented names only. Ada Lovelace, Anna van der Meer, j.doe and the mock client's people are fine.
Never the maintainer's name or a real person's.

## The test site

Never name the test site, its hostname, its project names or its people anywhere in the repo.
Say "the test site" and describe what it showed in general terms.
