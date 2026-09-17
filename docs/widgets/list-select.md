---
title: ListSelect
description: The former name of ListPicker.
---

ListSelect is now [ListPicker](list-picker.md). The `list-select` registry item stays for one
release and re-exports it.

```python
from sg_widgets_qt.widgets.list_picker import ListPicker
```

`sg_widgets_qt.widgets.list_select` re-exports that class under both names for one release. It
adds nothing of its own: the props, the signals and the keyboard are
[ListPicker](list-picker.md)'s.
