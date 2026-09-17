# The upstream half of the state matrix

One file per `(widget, state)`. Each is the body of the async function `~/dev/sg-widgets/tools/qa.mjs`
runs inside the page, so it has `$`, `$$`, `wait` and `harness`, and it leaves the page in the state
its name says before the driver takes the shot:

    cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/text-editor/ --framework react \
        --drive ~/dev/sg-widgets-qt/tools/drives/upstream/text-editor-draft.js \
        --shot /tmp/ref/text-editor-draft.png

The Qt half of the same state is `tools/drives/states/<widget>.py`, which reads the state from the
`QA_STATE` environment variable:

    QA_STATE=draft .venv/bin/python tools/qa.py --page text-editor \
        --drive tools/drives/states/text-editor.py --shot shots/states/text-editor-draft.png

Hover is not in the matrix: a drive runs inside the page and cannot make the browser hover, so the
hover, focus-visible, aria-invalid, disabled and read-only states are compared from the class
strings of the upstream component and its vendored primitives instead.
