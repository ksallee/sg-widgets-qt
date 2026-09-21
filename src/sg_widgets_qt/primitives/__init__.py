"""The shadcn primitives as custom painted Qt widgets.

Every leaf here is drawn by `paintEvent` from the theme's tokens, so none of them wears the host
style. `base` carries the ladders, the states, the motion and the chrome they share.

    from sg_widgets_qt.primitives import Button, Input, Badge
"""
from __future__ import annotations

from .accessible import *  # noqa: F403
from .accessible import __all__ as _accessible_all
from .badge import *  # noqa: F403
from .badge import __all__ as _badge_all
from .base import *  # noqa: F403
from .base import __all__ as _base_all
from .button import *  # noqa: F403
from .button import __all__ as _button_all
from .calendar import *  # noqa: F403
from .calendar import __all__ as _calendar_all
from .checkbox import *  # noqa: F403
from .checkbox import __all__ as _checkbox_all
from .command import *  # noqa: F403
from .command import __all__ as _command_all
from .dialog import *  # noqa: F403
from .dialog import __all__ as _dialog_all
from .dropdown_menu import *  # noqa: F403
from .dropdown_menu import __all__ as _dropdown_menu_all
from .hover_card import *  # noqa: F403
from .hover_card import __all__ as _hover_card_all
from .input import *  # noqa: F403
from .input import __all__ as _input_all
from .input_group import *  # noqa: F403
from .input_group import __all__ as _input_group_all
from .label import *  # noqa: F403
from .label import __all__ as _label_all
from .list_view import *  # noqa: F403
from .list_view import __all__ as _list_view_all
from .popover import *  # noqa: F403
from .popover import __all__ as _popover_all
from .roles import *  # noqa: F403
from .roles import __all__ as _roles_all
from .row_delegate import *  # noqa: F403
from .row_delegate import __all__ as _row_delegate_all
from .scrollbar import *  # noqa: F403
from .scrollbar import __all__ as _scrollbar_all
from .select import *  # noqa: F403
from .select import __all__ as _select_all
from .skeleton import *  # noqa: F403
from .skeleton import __all__ as _skeleton_all
from .table import *  # noqa: F403
from .table import __all__ as _table_all
from .tooltip import *  # noqa: F403
from .tooltip import __all__ as _tooltip_all

__all__ = [
    *_accessible_all,
    *_base_all,
    *_button_all,
    *_input_all,
    *_label_all,
    *_skeleton_all,
    *_badge_all,
    *_checkbox_all,
    *_roles_all,
    *_scrollbar_all,
    *_row_delegate_all,
    *_list_view_all,
    *_input_group_all,
    *_command_all,
    *_calendar_all,
    *_table_all,
    *_popover_all,
    *_dropdown_menu_all,
    *_select_all,
    *_hover_card_all,
    *_dialog_all,
    *_tooltip_all,
]
