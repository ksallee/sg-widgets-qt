---
title: ListMultiSelect
description: The former name of ListMultiPicker.
---

ListMultiSelect is now [ListMultiPicker](list-multi-picker.md). The `list-multi-select`
registry item stays for one release and re-exports it.

```python
from sg_widgets_qt.widgets.list_multi_picker import ListMultiPicker
```

`sg_widgets_qt.widgets.list_multi_select` re-exports that class under both names for one release.
It adds nothing of its own: the props, the signals and the keyboard are
[ListMultiPicker](list-multi-picker.md)'s.
