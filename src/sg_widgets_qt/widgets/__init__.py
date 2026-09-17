"""One module per registry item, each named after the item in snake_case.

Every widget here is a `QWidget` subclass drawn from the theme's tokens, taking its upstream props
as keyword arguments and emitting its upstream events as Qt signals.

    from sg_widgets_qt.widgets import StatusBadge, Thumbnail, UserAvatar
"""
from __future__ import annotations

from .checkbox_editor import *  # noqa: F403
from .checkbox_editor import __all__ as _checkbox_editor_all
from .color_editor import *  # noqa: F403
from .color_editor import __all__ as _color_editor_all
from .date_editor import *  # noqa: F403
from .date_editor import __all__ as _date_editor_all
from .date_time_editor import *  # noqa: F403
from .date_time_editor import __all__ as _date_time_editor_all
from .editor_calendar import *  # noqa: F403
from .editor_calendar import __all__ as _editor_calendar_all
from .entity_chip import *  # noqa: F403
from .entity_chip import __all__ as _entity_chip_all
from .entity_glyphs import *  # noqa: F403
from .entity_glyphs import __all__ as _entity_glyphs_all
from .entity_multi_picker import *  # noqa: F403
from .entity_multi_picker import __all__ as _entity_multi_picker_all
from .entity_picker import *  # noqa: F403
from .entity_picker import __all__ as _entity_picker_all
from .field_error import *  # noqa: F403
from .field_error import __all__ as _field_error_all
from .match_text import *  # noqa: F403
from .match_text import __all__ as _match_text_all
from .number_editor import *  # noqa: F403
from .number_editor import __all__ as _number_editor_all
from .picker_control import *  # noqa: F403
from .picker_control import __all__ as _picker_control_all
from .state_line import *  # noqa: F403
from .state_line import __all__ as _state_line_all
from .status_badge import *  # noqa: F403
from .status_badge import __all__ as _status_badge_all
from .status_glyph import *  # noqa: F403
from .status_glyph import __all__ as _status_glyph_all
from .text_editor import *  # noqa: F403
from .text_editor import __all__ as _text_editor_all
from .thumbnail import *  # noqa: F403
from .thumbnail import __all__ as _thumbnail_all
from .url_editor import *  # noqa: F403
from .url_editor import __all__ as _url_editor_all
from .user_avatar import *  # noqa: F403
from .user_avatar import __all__ as _user_avatar_all
from .value_editor import *  # noqa: F403
from .value_editor import __all__ as _value_editor_all

__all__ = [
    *_state_line_all,
    *_status_glyph_all,
    *_status_badge_all,
    *_thumbnail_all,
    *_user_avatar_all,
    *_match_text_all,
    *_entity_glyphs_all,
    *_entity_chip_all,
    *_value_editor_all,
    *_field_error_all,
    *_editor_calendar_all,
    *_text_editor_all,
    *_number_editor_all,
    *_checkbox_editor_all,
    *_date_editor_all,
    *_date_time_editor_all,
    *_url_editor_all,
    *_color_editor_all,
]

from .context_selector import *  # noqa: F403
from .context_selector import __all__ as _context_selector_all
from .global_search import *  # noqa: F403
from .global_search import __all__ as _global_search_all
from .hierarchical_search import *  # noqa: F403
from .hierarchical_search import __all__ as _hierarchical_search_all
from .picker_row import *  # noqa: F403
from .picker_row import __all__ as _picker_row_all
from .search_control import *  # noqa: F403
from .search_control import __all__ as _search_control_all
from .search_skeleton import *  # noqa: F403
from .search_skeleton import __all__ as _search_skeleton_all

__all__ = [
    *globals().get("__all__", []),
    *_picker_row_all,
    *_search_skeleton_all,
    *_search_control_all,
    *_global_search_all,
    *_hierarchical_search_all,
    *_context_selector_all,
    *_picker_control_all,
    *_entity_picker_all,
    *_entity_multi_picker_all,
]

from .entity_card import *  # noqa: F403
from .entity_card import __all__ as _entity_card_all
from .field_value import *  # noqa: F403
from .field_value import __all__ as _field_value_all

__all__ = [
    *globals().get("__all__", []),
    *_entity_card_all,
    *_field_value_all,
]

from .entity_type_multi_picker import *  # noqa: F403
from .entity_type_multi_picker import __all__ as _entity_type_multi_picker_all
from .entity_type_picker import *  # noqa: F403
from .entity_type_picker import __all__ as _entity_type_picker_all
from .list_multi_picker import *  # noqa: F403
from .list_multi_picker import __all__ as _list_multi_picker_all
from .list_multi_select import *  # noqa: F403
from .list_multi_select import __all__ as _list_multi_select_all
from .list_picker import *  # noqa: F403
from .list_picker import __all__ as _list_picker_all
from .list_select import *  # noqa: F403
from .list_select import __all__ as _list_select_all
from .project_multi_picker import *  # noqa: F403
from .project_multi_picker import __all__ as _project_multi_picker_all
from .project_picker import *  # noqa: F403
from .project_picker import __all__ as _project_picker_all
from .status_multi_picker import *  # noqa: F403
from .status_multi_picker import __all__ as _status_multi_picker_all
from .status_picker import *  # noqa: F403
from .status_picker import __all__ as _status_picker_all
from .user_multi_picker import *  # noqa: F403
from .user_multi_picker import __all__ as _user_multi_picker_all
from .user_picker import *  # noqa: F403
from .user_picker import __all__ as _user_picker_all

__all__ = [
    *globals().get("__all__", []),
    *_user_picker_all,
    *_user_multi_picker_all,
    *_project_picker_all,
    *_project_multi_picker_all,
    *_list_picker_all,
    *_list_multi_picker_all,
    *_list_select_all,
    *_list_multi_select_all,
    *_status_picker_all,
    *_status_multi_picker_all,
    *_entity_type_picker_all,
    *_entity_type_multi_picker_all,
]

from .column_picker import *  # noqa: F403
from .column_picker import __all__ as _column_picker_all
from .field_editor import *  # noqa: F403
from .field_editor import __all__ as _field_editor_all
from .field_picker import *  # noqa: F403
from .field_picker import __all__ as _field_picker_all

__all__ = [
    *globals().get("__all__", []),
    *_field_picker_all,
    *_column_picker_all,
    *_field_editor_all,
]

from .filter_bar import *  # noqa: F403
from .filter_bar import __all__ as _filter_bar_all
from .filter_dialog import *  # noqa: F403
from .filter_dialog import __all__ as _filter_dialog_all
from .filter_editor import *  # noqa: F403
from .filter_editor import __all__ as _filter_editor_all
from .sort_picker import *  # noqa: F403
from .sort_picker import __all__ as _sort_picker_all

__all__ = [
    *globals().get("__all__", []),
    *_filter_editor_all,
    *_filter_dialog_all,
    *_filter_bar_all,
    *_sort_picker_all,
]
