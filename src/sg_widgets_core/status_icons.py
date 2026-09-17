"""Stock status icons.

A status with an `image_map` icon names a CSS class such as `icon_apr`. The image
behind it is one sprite the web app serves unauthenticated at
`/images/sg_icon_image_map.png`, positioned by rules in
`/dist/production/stylesheets/login.css` (probe 010). Neither is in the REST API.
The offsets below are those rules, read once. The data URLs are the sprite cells of
every icon the status picker offers (`icon_type: permanent_status`, 94 on the probed
site), so a badge renders any stock status icon with no site access.

A shipped status is a row with no `created_by`. `system` marks a subset of them
(act, dis, ip, na, cfrm, pndng) and no schema flag marks the set; a site may
have retired some of the shipped rows (probe 061).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

__all__ = [
    "NATIVE_STATUSES",
    "STOCK_ICON_CELLS",
    "STOCK_ICON_DATA_URLS",
    "STOCK_ICON_KEYS",
    "STOCK_SPRITE_PATH",
    "DataIconSource",
    "NativeStatus",
    "NoIconSource",
    "SpriteCell",
    "SpriteIconSource",
    "StockIconSource",
    "is_native_status",
    "native_status",
    "sprite_style",
    "stock_icon_source",
]


@dataclass
class SpriteCell:
    x: int
    y: int
    w: int
    h: int


#: Path of the stock sprite on any site. The stylesheet appends a cache-busting query; the bare path answers 200.
STOCK_SPRITE_PATH = "/images/sg_icon_image_map.png"


@dataclass
class NativeStatus:
    code: str
    name: str
    #: `image_map_key` of the shipped icon. `act` has an html icon and no key.
    image_map_key: str | None
    #: Locked by the system: cannot be deleted.
    system: bool


NATIVE_STATUSES: tuple[NativeStatus, ...] = (
    NativeStatus(code="act", name="Active", image_map_key=None, system=True),
    NativeStatus(code="apr", name="Approved", image_map_key="icon_apr", system=False),
    NativeStatus(code="clsd", name="Closed", image_map_key="icon_fin", system=False),
    NativeStatus(code="cmpt", name="Complete", image_map_key="icon_cmpt", system=False),
    NativeStatus(code="dis", name="Disabled", image_map_key="icon_na", system=True),
    NativeStatus(code="fin", name="Final", image_map_key="icon_fin", system=False),
    NativeStatus(code="hld", name="On Hold", image_map_key="icon_hld", system=False),
    NativeStatus(code="ip", name="In Progress", image_map_key="icon_ip", system=True),
    NativeStatus(code="na", name="N/A", image_map_key="icon_na", system=True),
    NativeStatus(code="omt", name="Omit", image_map_key="icon_omt", system=False),
    NativeStatus(code="opn", name="Open", image_map_key="icon_rdy", system=False),
    NativeStatus(code="res", name="Resolved", image_map_key="icon_fin", system=False),
    NativeStatus(code="rev", name="Pending Review", image_map_key="icon_rev", system=False),
    NativeStatus(code="wtg", name="Waiting to Start", image_map_key="icon_wtg", system=False),
    NativeStatus(code="vwd", name="Viewed", image_map_key="icon_fin", system=False),
    NativeStatus(code="recd", name="Received", image_map_key="icon_recd", system=False),
    NativeStatus(code="dlvr", name="Delivered", image_map_key="icon_dlvr", system=False),
    NativeStatus(code="cfrm", name="Confirmed", image_map_key="icon_thumb_up", system=True),
    NativeStatus(code="pndng", name="Pending", image_map_key="icon_voice_command", system=True),
)
"""Shipped statuses the probed site keeps live, in id order (probe 061)."""

STOCK_ICON_CELLS: dict[str, SpriteCell] = {
    "icon_activity": SpriteCell(x=240, y=107, w=16, h=15),
    "icon_airplane": SpriteCell(x=314, y=538, w=16, h=16),
    "icon_alert": SpriteCell(x=330, y=538, w=16, h=16),
    "icon_annotation": SpriteCell(x=296, y=748, w=31, h=30),
    "icon_announcement": SpriteCell(x=346, y=538, w=16, h=16),
    "icon_apr": SpriteCell(x=89, y=11, w=12, h=11),
    "icon_arrow_down": SpriteCell(x=126, y=79, w=14, h=14),
    "icon_arrow_down_dark": SpriteCell(x=362, y=538, w=16, h=16),
    "icon_arrow_head_right": SpriteCell(x=54, y=619, w=12, h=18),
    "icon_arrow_left": SpriteCell(x=378, y=538, w=16, h=16),
    "icon_arrow_right": SpriteCell(x=70, y=65, w=15, h=14),
    "icon_arrow_right2": SpriteCell(x=0, y=554, w=16, h=16),
    "icon_arrow_thin_down": SpriteCell(x=36, y=0, w=5, h=6),
    "icon_arrow_thin_left": SpriteCell(x=176, y=602, w=19, h=17),
    "icon_arrow_thin_up": SpriteCell(x=41, y=0, w=5, h=6),
    "icon_arrow_up": SpriteCell(x=140, y=79, w=14, h=14),
    "icon_arrow_up_dark": SpriteCell(x=16, y=554, w=16, h=16),
    "icon_asg": SpriteCell(x=32, y=554, w=16, h=16),
    "icon_attachment_white": SpriteCell(x=34, y=638, w=18, h=19),
    "icon_auction": SpriteCell(x=48, y=554, w=16, h=16),
    "icon_award": SpriteCell(x=64, y=554, w=16, h=16),
    "icon_back": SpriteCell(x=154, y=79, w=15, h=14),
    "icon_bell": SpriteCell(x=80, y=554, w=16, h=16),
    "icon_bicycle": SpriteCell(x=96, y=554, w=16, h=16),
    "icon_blocked": SpriteCell(x=169, y=79, w=14, h=14),
    "icon_blue": SpriteCell(x=183, y=79, w=14, h=14),
    "icon_bluered": SpriteCell(x=197, y=79, w=14, h=14),
    "icon_bluered_check": SpriteCell(x=211, y=79, w=14, h=14),
    "icon_box": SpriteCell(x=225, y=79, w=14, h=14),
    "icon_browser_overlay_player": SpriteCell(x=304, y=506, w=16, h=16),
    "icon_bug": SpriteCell(x=112, y=554, w=16, h=16),
    "icon_c": SpriteCell(x=239, y=79, w=14, h=14),
    "icon_c_black": SpriteCell(x=70, y=23, w=12, h=12),
    "icon_calculator": SpriteCell(x=128, y=554, w=16, h=16),
    "icon_calendar": SpriteCell(x=144, y=554, w=16, h=16),
    "icon_calendar_edit": SpriteCell(x=83, y=0, w=7, h=8),
    "icon_calendar_view": SpriteCell(x=274, y=11, w=13, h=12),
    "icon_car": SpriteCell(x=160, y=554, w=16, h=16),
    "icon_car_dark": SpriteCell(x=176, y=554, w=16, h=16),
    "icon_card_view": SpriteCell(x=207, y=0, w=13, h=9),
    "icon_carnation": SpriteCell(x=253, y=79, w=14, h=14),
    "icon_cbb": SpriteCell(x=267, y=79, w=14, h=14),
    "icon_chain_link": SpriteCell(x=256, y=107, w=15, h=15),
    "icon_check": SpriteCell(x=192, y=554, w=16, h=16),
    "icon_check_blue": SpriteCell(x=101, y=11, w=12, h=11),
    "icon_check_orange": SpriteCell(x=113, y=11, w=12, h=11),
    "icon_checkmark_small_white": SpriteCell(x=287, y=11, w=12, h=12),
    "icon_checkmark_thin_white": SpriteCell(x=90, y=0, w=13, h=8),
    "icon_chili": SpriteCell(x=309, y=79, w=14, h=14),
    "icon_chili2": SpriteCell(x=281, y=79, w=14, h=14),
    "icon_chili3": SpriteCell(x=295, y=79, w=14, h=14),
    "icon_client_final": SpriteCell(x=70, y=122, w=18, h=15),
    "icon_clock": SpriteCell(x=323, y=79, w=14, h=14),
    "icon_clock_dark": SpriteCell(x=208, y=554, w=16, h=16),
    "icon_cmpt": SpriteCell(x=337, y=79, w=14, h=14),
    "icon_coffee_cup": SpriteCell(x=224, y=554, w=16, h=16),
    "icon_coffee_mug": SpriteCell(x=240, y=554, w=16, h=16),
    "icon_comment": SpriteCell(x=195, y=602, w=17, h=17),
    "icon_construction": SpriteCell(x=256, y=554, w=16, h=16),
    "icon_construction_hat": SpriteCell(x=272, y=554, w=16, h=16),
    "icon_cool": SpriteCell(x=288, y=554, w=16, h=16),
    "icon_cowbell": SpriteCell(x=304, y=554, w=16, h=16),
    "icon_cursor": SpriteCell(x=320, y=554, w=16, h=16),
    "icon_cut": SpriteCell(x=336, y=554, w=16, h=16),
    "icon_dailies": SpriteCell(x=351, y=79, w=14, h=14),
    "icon_dashboard": SpriteCell(x=352, y=554, w=16, h=16),
    "icon_delete": SpriteCell(x=368, y=554, w=16, h=16),
    "icon_delivery_truck": SpriteCell(x=384, y=554, w=16, h=16),
    "icon_design_page": SpriteCell(x=320, y=506, w=16, h=16),
    "icon_dlvr": SpriteCell(x=88, y=122, w=17, h=15),
    "icon_down_facing_arrow_circle": SpriteCell(x=225, y=721, w=27, h=27),
    "icon_download": SpriteCell(x=212, y=602, w=17, h=17),
    "icon_drag_drop_handle": SpriteCell(x=386, y=0, w=11, h=11),
    "icon_e": SpriteCell(x=365, y=79, w=14, h=14),
    "icon_edit": SpriteCell(x=311, y=11, w=12, h=12),
    "icon_edit_disabled": SpriteCell(x=335, y=11, w=12, h=12),
    "icon_edit_selected": SpriteCell(x=170, y=23, w=14, h=13),
    "icon_email": SpriteCell(x=220, y=0, w=13, h=9),
    "icon_email2": SpriteCell(x=0, y=570, w=16, h=16),
    "icon_email_open": SpriteCell(x=16, y=570, w=16, h=16),
    "icon_email_password": SpriteCell(x=0, y=721, w=23, h=23),
    "icon_exchange": SpriteCell(x=32, y=570, w=16, h=16),
    "icon_expand": SpriteCell(x=48, y=570, w=16, h=16),
    "icon_export_excel": SpriteCell(x=336, y=506, w=16, h=16),
    "icon_eye": SpriteCell(x=64, y=570, w=16, h=16),
    "icon_f": SpriteCell(x=379, y=79, w=14, h=14),
    "icon_fan": SpriteCell(x=80, y=570, w=16, h=16),
    "icon_favorite": SpriteCell(x=96, y=570, w=16, h=16),
    "icon_filter": SpriteCell(x=352, y=506, w=15, h=16),
    "icon_filter_active": SpriteCell(x=367, y=506, w=15, h=16),
    "icon_filter_menu": SpriteCell(x=196, y=699, w=21, h=22),
    "icon_fin": SpriteCell(x=128, y=0, w=7, h=8),
    "icon_financial": SpriteCell(x=112, y=570, w=16, h=16),
    "icon_first_aid_box": SpriteCell(x=128, y=570, w=16, h=16),
    "icon_flag": SpriteCell(x=144, y=570, w=16, h=16),
    "icon_flag_red": SpriteCell(x=0, y=93, w=14, h=14),
    "icon_flash": SpriteCell(x=160, y=570, w=16, h=16),
    "icon_follow_link_large": SpriteCell(x=100, y=657, w=20, h=20),
    "icon_formatting": SpriteCell(x=85, y=65, w=15, h=14),
    "icon_gear": SpriteCell(x=322, y=0, w=10, h=10),
    "icon_gift": SpriteCell(x=176, y=570, w=16, h=16),
    "icon_gift_card": SpriteCell(x=192, y=570, w=16, h=16),
    "icon_go_to_bottom": SpriteCell(x=208, y=570, w=16, h=16),
    "icon_go_to_top": SpriteCell(x=224, y=570, w=16, h=16),
    "icon_green_circle_dot": SpriteCell(x=240, y=570, w=16, h=16),
    "icon_green_d": SpriteCell(x=14, y=93, w=14, h=14),
    "icon_grid_view": SpriteCell(x=53, y=0, w=13, h=7),
    "icon_gym": SpriteCell(x=256, y=570, w=16, h=16),
    "icon_hammer": SpriteCell(x=272, y=570, w=16, h=16),
    "icon_hand": SpriteCell(x=288, y=570, w=16, h=16),
    "icon_hand_pointer": SpriteCell(x=304, y=570, w=16, h=16),
    "icon_help": SpriteCell(x=320, y=570, w=16, h=16),
    "icon_help_balloon_sm": SpriteCell(x=66, y=619, w=18, h=18),
    "icon_help_round": SpriteCell(x=100, y=65, w=14, h=14),
    "icon_hld": SpriteCell(x=66, y=0, w=5, h=7),
    "icon_hot": SpriteCell(x=336, y=570, w=16, h=16),
    "icon_hourglass": SpriteCell(x=352, y=570, w=16, h=16),
    "icon_if": SpriteCell(x=28, y=93, w=14, h=14),
    "icon_import_csv": SpriteCell(x=382, y=506, w=16, h=16),
    "icon_inbox_clear": SpriteCell(x=114, y=65, w=14, h=14),
    "icon_inbox_gear": SpriteCell(x=0, y=522, w=16, h=16),
    "icon_inbox_refresh": SpriteCell(x=217, y=699, w=20, h=22),
    "icon_inbox_search": SpriteCell(x=271, y=107, w=15, h=15),
    "icon_info_dark": SpriteCell(x=347, y=11, w=12, h=12),
    "icon_invite_people": SpriteCell(x=84, y=619, w=14, h=18),
    "icon_ip": SpriteCell(x=332, y=0, w=10, h=10),
    "icon_ip25": SpriteCell(x=42, y=93, w=28, h=14),
    "icon_ip50": SpriteCell(x=70, y=93, w=28, h=14),
    "icon_ip75": SpriteCell(x=98, y=93, w=28, h=14),
    "icon_jira_bridge": SpriteCell(x=128, y=65, w=14, h=14),
    "icon_jump": SpriteCell(x=32, y=522, w=16, h=16),
    "icon_key": SpriteCell(x=368, y=570, w=16, h=16),
    "icon_kick": SpriteCell(x=126, y=93, w=14, h=14),
    "icon_light_bulb": SpriteCell(x=384, y=570, w=16, h=16),
    "icon_linked_file": SpriteCell(x=142, y=65, w=14, h=14),
    "icon_lock": SpriteCell(x=156, y=65, w=14, h=14),
    "icon_lock2": SpriteCell(x=0, y=586, w=16, h=16),
    "icon_lock_small": SpriteCell(x=184, y=23, w=11, h=13),
    "icon_login": SpriteCell(x=16, y=586, w=16, h=16),
    "icon_logout": SpriteCell(x=32, y=586, w=16, h=16),
    "icon_manage_shares": SpriteCell(x=170, y=65, w=16, h=14),
    "icon_martini_glass": SpriteCell(x=48, y=586, w=16, h=16),
    "icon_media": SpriteCell(x=252, y=721, w=27, h=27),
    "icon_media_active": SpriteCell(x=279, y=721, w=27, h=27),
    "icon_media_playlist": SpriteCell(x=110, y=721, w=19, h=24),
    "icon_menu_arrow_down": SpriteCell(x=233, y=0, w=9, h=9),
    "icon_menu_arrow_up": SpriteCell(x=242, y=0, w=9, h=9),
    "icon_microphone": SpriteCell(x=64, y=586, w=16, h=16),
    "icon_mode_cal_on": SpriteCell(x=98, y=619, w=25, h=18),
    "icon_mode_link_off": SpriteCell(x=123, y=619, w=25, h=18),
    "icon_mode_link_on": SpriteCell(x=148, y=619, w=25, h=18),
    "icon_mode_note_off": SpriteCell(x=173, y=619, w=25, h=18),
    "icon_mode_note_on": SpriteCell(x=198, y=619, w=25, h=18),
    "icon_music": SpriteCell(x=80, y=586, w=16, h=16),
    "icon_mute": SpriteCell(x=359, y=11, w=15, h=12),
    "icon_mute_active": SpriteCell(x=374, y=11, w=15, h=12),
    "icon_my_tasks_new_task": SpriteCell(x=282, y=0, w=10, h=10),
    "icon_na": SpriteCell(x=46, y=0, w=7, h=6),
    "icon_nested_grouping": SpriteCell(x=195, y=23, w=12, h=13),
    "icon_new_page": SpriteCell(x=48, y=522, w=19, h=16),
    "icon_notes": SpriteCell(x=140, y=93, w=14, h=14),
    "icon_office_chair": SpriteCell(x=96, y=586, w=16, h=16),
    "icon_omt": SpriteCell(x=154, y=93, w=14, h=14),
    "icon_package_box": SpriteCell(x=112, y=586, w=16, h=16),
    "icon_padlock": SpriteCell(x=306, y=107, w=20, h=15),
    "icon_padlock_large": SpriteCell(x=23, y=721, w=18, h=23),
    "icon_padlock_unlocked": SpriteCell(x=346, y=107, w=20, h=15),
    "icon_page_settings": SpriteCell(x=186, y=65, w=19, h=14),
    "icon_page_settings_dirty": SpriteCell(x=205, y=65, w=19, h=14),
    "icon_paperclip": SpriteCell(x=237, y=65, w=13, h=14),
    "icon_phone": SpriteCell(x=128, y=586, w=16, h=16),
    "icon_player_close_x": SpriteCell(x=52, y=638, w=13, h=19),
    "icon_player_pan": SpriteCell(x=357, y=748, w=30, h=30),
    "icon_plus": SpriteCell(x=292, y=0, w=10, h=10),
    "icon_plus_dark": SpriteCell(x=0, y=23, w=12, h=12),
    "icon_plus_white": SpriteCell(x=111, y=0, w=8, h=8),
    "icon_preferences": SpriteCell(x=264, y=65, w=14, h=14),
    "icon_purple_circle_line": SpriteCell(x=168, y=93, w=14, h=14),
    "icon_push_pinned_task": SpriteCell(x=366, y=107, w=19, h=15),
    "icon_puzzle": SpriteCell(x=144, y=586, w=16, h=16),
    "icon_question": SpriteCell(x=182, y=93, w=14, h=14),
    "icon_r": SpriteCell(x=105, y=122, w=20, h=15),
    "icon_rdy": SpriteCell(x=342, y=0, w=10, h=10),
    "icon_recd": SpriteCell(x=196, y=93, w=14, h=14),
    "icon_redo": SpriteCell(x=210, y=93, w=14, h=14),
    "icon_redo_again": SpriteCell(x=160, y=586, w=16, h=16),
    "icon_reprocess": SpriteCell(x=125, y=122, w=14, h=15),
    "icon_restrict": SpriteCell(x=176, y=586, w=16, h=16),
    "icon_rev": SpriteCell(x=314, y=23, w=12, h=13),
    "icon_revert": SpriteCell(x=293, y=65, w=15, h=14),
    "icon_right_facing_arrow_circle": SpriteCell(x=306, y=721, w=27, h=27),
    "icon_rocket": SpriteCell(x=192, y=586, w=16, h=16),
    "icon_satellite": SpriteCell(x=208, y=586, w=16, h=16),
    "icon_save": SpriteCell(x=308, y=65, w=15, h=14),
    "icon_search": SpriteCell(x=220, y=678, w=21, h=21),
    "icon_search_active": SpriteCell(x=241, y=678, w=21, h=21),
    "icon_search_active_open": SpriteCell(x=262, y=678, w=21, h=21),
    "icon_search_open": SpriteCell(x=283, y=678, w=21, h=21),
    "icon_security": SpriteCell(x=224, y=586, w=16, h=16),
    "icon_sent": SpriteCell(x=238, y=93, w=14, h=14),
    "icon_settings": SpriteCell(x=247, y=602, w=18, h=17),
    "icon_settings_dense": SpriteCell(x=210, y=522, w=16, h=16),
    "icon_share": SpriteCell(x=89, y=522, w=13, h=16),
    "icon_share_large_blue": SpriteCell(x=41, y=721, w=18, h=23),
    "icon_share_large_white": SpriteCell(x=59, y=721, w=18, h=23),
    "icon_share_small": SpriteCell(x=207, y=23, w=11, h=13),
    "icon_share_small_dark": SpriteCell(x=323, y=65, w=14, h=14),
    "icon_shovel": SpriteCell(x=240, y=586, w=16, h=16),
    "icon_shuffle": SpriteCell(x=256, y=586, w=16, h=16),
    "icon_small_white_play": SpriteCell(x=304, y=678, w=22, h=21),
    "icon_sofa_chair": SpriteCell(x=272, y=586, w=16, h=16),
    "icon_sport": SpriteCell(x=288, y=586, w=16, h=16),
    "icon_square_empty": SpriteCell(x=82, y=23, w=12, h=12),
    "icon_square_purple_100": SpriteCell(x=106, y=23, w=12, h=12),
    "icon_square_purple_50": SpriteCell(x=94, y=23, w=12, h=12),
    "icon_star": SpriteCell(x=304, y=586, w=16, h=16),
    "icon_stop": SpriteCell(x=320, y=586, w=16, h=16),
    "icon_stopped": SpriteCell(x=252, y=93, w=14, h=14),
    "icon_t": SpriteCell(x=266, y=93, w=14, h=14),
    "icon_tab_two_pane": SpriteCell(x=0, y=11, w=13, h=11),
    "icon_tab_url": SpriteCell(x=337, y=65, w=14, h=14),
    "icon_techfix": SpriteCell(x=280, y=93, w=14, h=14),
    "icon_template": SpriteCell(x=229, y=23, w=13, h=13),
    "icon_thumb_column_header": SpriteCell(x=13, y=11, w=15, h=11),
    "icon_thumb_down": SpriteCell(x=336, y=586, w=16, h=16),
    "icon_thumb_up": SpriteCell(x=352, y=586, w=16, h=16),
    "icon_thumbnail_view": SpriteCell(x=251, y=0, w=13, h=9),
    "icon_thumbs_down": SpriteCell(x=294, y=93, w=14, h=14),
    "icon_thumbs_up": SpriteCell(x=308, y=93, w=14, h=14),
    "icon_to": SpriteCell(x=322, y=93, w=14, h=14),
    "icon_today_dense": SpriteCell(x=162, y=522, w=16, h=16),
    "icon_tool_box": SpriteCell(x=368, y=586, w=16, h=16),
    "icon_tooltip": SpriteCell(x=365, y=65, w=14, h=14),
    "icon_trash": SpriteCell(x=384, y=586, w=16, h=16),
    "icon_trash_crs": SpriteCell(x=102, y=522, w=12, h=16),
    "icon_triangle_blue_100": SpriteCell(x=137, y=11, w=12, h=11),
    "icon_triangle_blue_50": SpriteCell(x=125, y=11, w=12, h=11),
    "icon_triangle_grey": SpriteCell(x=149, y=11, w=12, h=11),
    "icon_trophy": SpriteCell(x=0, y=602, w=16, h=16),
    "icon_umbella": SpriteCell(x=16, y=602, w=16, h=16),
    "icon_undo": SpriteCell(x=32, y=602, w=16, h=16),
    "icon_unlock": SpriteCell(x=48, y=602, w=16, h=16),
    "icon_unpin_task": SpriteCell(x=379, y=65, w=15, h=14),
    "icon_uploaded_file": SpriteCell(x=385, y=107, w=14, h=15),
    "icon_url": SpriteCell(x=114, y=522, w=16, h=16),
    "icon_view_eye": SpriteCell(x=28, y=11, w=21, h=11),
    "icon_voice_command": SpriteCell(x=64, y=602, w=16, h=16),
    "icon_walk": SpriteCell(x=80, y=602, w=16, h=16),
    "icon_warning": SpriteCell(x=130, y=522, w=16, h=16),
    "icon_weather": SpriteCell(x=96, y=602, w=16, h=16),
    "icon_web": SpriteCell(x=0, y=79, w=14, h=14),
    "icon_webhooks": SpriteCell(x=146, y=522, w=16, h=16),
    "icon_wrap_text": SpriteCell(x=49, y=11, w=14, h=11),
    "icon_wrench": SpriteCell(x=242, y=23, w=14, h=13),
    "icon_wtg": SpriteCell(x=1, y=0, w=4, h=1),
    "icon_x_in_circle": SpriteCell(x=178, y=721, w=26, h=26),
    "icon_x_no_shadow": SpriteCell(x=302, y=0, w=10, h=10),
    "icon_x_thin_white": SpriteCell(x=119, y=0, w=9, h=8),
    "icon_yellow_circle_line": SpriteCell(x=336, y=93, w=14, h=14),
    "icon_zoom": SpriteCell(x=131, y=748, w=29, h=28),
    "icon_zoom_in_dense": SpriteCell(x=178, y=522, w=16, h=16),
    "icon_zoom_out_dense": SpriteCell(x=194, y=522, w=16, h=16),
    "icon_zoom_task_dependencies": SpriteCell(x=14, y=79, w=14, h=14),
}
"""Sprite cell per `image_map_key`, from the site stylesheet. Covers every stock icon a status may use."""

STOCK_ICON_DATA_URLS: dict[str, str] = {
    "icon_airplane":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA/0lEQVQ4jZ2S4W3CMBCFvUFG6CAo4kdCCaERcmxMjNMEEFCKijpCR8gIHaEjMIJHyCiHHkqjtqJR8Emf9Hx37ymKzVhHvZ3ePwFzrdfjiYBzwMvhSMA5YLc/EHAOWG+2BJzMRbkelqsNAejeRpMXDyYvvvLnkn6CHmb/GrU2ntbmQy9z6gQ72ni/zHOVlUpltVpo6oXKaniuZiHVWUhFf7Byvqi+z422N/bOjHNBnAvLuajSVM7SVLaf18zaW8AMO9htPNT5Q5NkRoC5VBw/edNpQgD6LvN4PPGiKLZRFFODRa93QBCENghGFIaPFYBGr3fAYODXvj9sXx80erd2L0GRrQda+R50AAAAAElFTkSuQmCC",
    "icon_alert":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA8klEQVQ4jbXS4Y2CMBQHcDZwBAchhhA/yCkBJeDJVS0pV8XjwgodwREchVEc4Y3wzLtUg1pFTK7JL2lf+/9/IFjWf62fsuqVvxUQ2ncuKHblodiVqB06hb/l1pGbApto9nKByGUtcokilyByedT7+qUwzwTnmUAt5JlwGmf+NPzFVj22XANbrlELtfMZ6M3DgjRlKk0ZNuwNM2UMx8lnP5kv8EatXc3p7V1BFMV1FMVoAIbZ9QcNgqkThjPsgjKXgokfHH0/QAOl3d1R5i/seWPleWM0GY0+FHl0T1nLdYfgukN8E1i2PQDbHuCboPXPbFsnGqkLsBB4i/EAAAAASUVORK5CYII=",
    "icon_announcement":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABAklEQVQ4jcXS3W3CMBAH8NuAUTpBlJeE2M4lpkVFRdDGOHWaFFRGyAiMkBEYISMwAiMwwlVXNeqHEAXy0L/0k+9Osl98AP+V5eqtZnBNymp5U72uiMG5cUWpXVFuXFHui5eKOnAqNnfa5q6xuTvkzwUdA5mxa9ZdyozVmbGNMfZgFjn9BeaPGbHZ/Gnb1ZeA6XRGfcBk8kB9wHh8T32A1rfERqO7tqsvAYjplvEPIKYtYrpPEu1jomvEtEFM6RT4HinjRsqYhFC1EMoXQn30UsYbpXCgFPpSxmvuP+c/H4giOQiC4S4IQvoy3PH895KFYdSyoxvoeX7meX7N59m7fm3eAd4KIY4RWEmZAAAAAElFTkSuQmCC",
    "icon_apr":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAALCAYAAABLcGxfAAAACXBIWXMAAAsSAAALEgHS3X78AAAAy0lEQVQokWNgQAd9DAYMfQwOYBoK1NTUBNTU1M6rqaklICsEKbrP0MfwHwmD+A5qamrr1dTU/iM0QBT/Z5jK8J/hFMN/hntQeirDfwlfCZBCEO5HNv0+WPEnhv9Mb5j+M/xkAGPhCcJgxZKeku/R3Qw2Ud5P/r9stCxYMd8qPrBiWXdZmPMMUJ1zD2EiSBOIBhnAdJEJpsEBwwaQyTDFig6KEOeBxFFswOIHiVKJ/+wX2cF8sDhIHi3scYYSqnMwNWGNB0zFBGIaGQAA30eIiQoxNjkAAAAASUVORK5CYII=",
    "icon_arrow_down_dark":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA30lEQVQ4jZXRbQrCMAwG4N2gF5Lhj6lzs5Ruozgmk+LHHI5dIUfyKDlSpIiCwWkMPFDa9KUfUfShrsMI12EkBiJpXfoBLv1AjDzg3PVw7npi5AHHUwfHU0eMPMD7A3h/IEYe0O49tHtPjDyg2bXQ7Fpi5AF13UBdN8TIA5zbgnNbYqYDysrdysrRn26vgKKolLUlWluSEIY9b6cwxiqtDWpt6AcMvR+vstFG5bnGPNc0AUPP1wfMso1K0wzTNCMGw5roF1artUqSJSbJgh6WGOZEm58Vx3M1m8UYhPFU3x1VxN4T1OzzJgAAAABJRU5ErkJggg==",
    "icon_arrow_left":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAx0lEQVQ4jbXTQW6DMBCF4bnBXCvEcaGAAZeE4Do4JpZyhRypR5kjTeUFUrJKbam/9C3f7AbgP7qFO97C/Sdr7NeAfg3k18DJ48V5XJwnd105Shp/2wXtxZG9ON78eTwbi7OxZIzlZ7Oxj3fgNM04nQ1NZ8M54Gs80XicOBdoPZLWI+eCvteouoFUN3AOiLWqx6ZR1DSKX7Td4x3YqusWq6qmqqp5A6mV5SdKWZKUJUfJB2KHwwcKIUkImXcgVhQCd7t93jOl9gsxjuQ4b7SgiAAAAABJRU5ErkJggg==",
    "icon_arrow_right2":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAs0lEQVQ4jb3TTQ6CMBCG4d6AIyEmIIj8iaiIFopAoQln4EgcZY40LiSRsBApiZM823fTr4T84xrR9o1oFekArwXyWkDFG7lIWdU4gKLkyyMsL3AEGHt+IjRl3Zw0y3ECaMrekeROURLckodC4jjBFYBE5yuuACQMI5QEp+iiEN8/dnM8L8AJCILw9+c8OB6OgOv6y7ZgWTYOwLad5UPS9R0ahgmmuZebsqpuek3byn+mb/cCncPgFWTUjwsAAAAASUVORK5CYII=",
    "icon_arrow_up_dark":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA3ElEQVQ4jZXQXQrCMAzA8d2g9xkyfBkyVIqMiWOy2bnPatEb5EgeJUeKFEUwOI2B30vb/B8aBBNzdhd1dld8uKjgnxmtU/bk0J4cPaE/Ey13/aj6wWI/WGLQ331dbtpetd2AbTfQBPRvPi4bc1SmbtDUDf2A/u3bclkZVR1qrA41CaHfeQWKfXkr9iX96Tb5F3leQJ4XxEAgnWy7g2y7I0YeSNMM0jQjRh7QegNab4iRB1ZrDau1JkYeSJIlJMmSGHkgjhcQxwti5IEomkMUzYmRB8JwBmE4I+Zj4A5d+OFxpP3AlQAAAABJRU5ErkJggg==",
    "icon_auction":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABMUlEQVQ4jZWS7W2DMBCG2cAjZAQWQKgSRaEQBweDA+VbRCQExEqM5BEygke4ipQfqcA0nPTolU/yY59lRVmoe9ujtut52/Xi3vaqsrWae7e7NR380opb026T1NdmqK8NvCDqa/OepLrUQ3WpYQFRXep1SVFWQ1lWIKMoKzHblGYFSrNil+XlkOUl/AOfCeIk43GSwRpJmufjIYvXjqJYRFEMKzzC8BtJ5z6fI5WxUDAWwgKPKXnAQrmE+kylPhPUZ/BC7gdnRH3Gn2sacEoDueR0oiohniDEg4nnzJ7nI0I8PvXGlEuOR6Ji7AqM3T+v7bonNPYwdmFKuUSR1AG7yHEwdxwMY9r2Ybtk3GRZNrcsG8bc77+2S0xzjwzD5IZhgmF8zj/WO6XrH0jTdK5pOvwAU6jYeS/2aloAAAAASUVORK5CYII=",
    "icon_award":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABa0lEQVQ4jY2T3W2DMBSF2YARMkLfUSSSB0JpSRFxnQImEAg/AYEYISMwQkfoCIzACIzgEVzdlESGQFRLn3w5556LjIwgTKyirKqirJqirGhRVl1fi8J/VpaXTZaXbAKa5YXxNJykWZWec8bRpuec8s9Jmr3MDojitIvilAFxcr6+LUkzMYrThtP9yXAQnBZBGLGeZuCFkcx535MDjsFJ9I8h9Y8h8/yg5T3PDwzQey6zRyCuR4nrMcAhh9ohB9EhB5m4XnvTietVswNsm/i2TdgTWstypgd84i8R7y2K91bb72xE1+sUeh8G7BCuEcIM2CHcIYQbhDDt93b3V9/8ehA2DHNhGCYbQU0TiQDUE/7iPkDXPxp9azCe7da4f22oxz5krqamvctvbzob0Y2PCNq4D7KCoqjdZvP6o6raRVFUBqiq9nDnQeP8C2QgO2iS5XW3Wq0Ht5Bf4EHPnC9I0rKWpOXszwIe9PDaL6tEDkltxDreAAAAAElFTkSuQmCC",
    "icon_bell":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA4klEQVQ4jZ3S2wnCMBQG4G7gQF6CT15qSdFSCVZi25S0oSEjZCRH6CgdwRGORIIovRh74INDyP+/JJ7XM7VUs1qqey0VWI33z1RCqkpIqIRsLbMr5wJeCs1LAbwUyDK7dgqzglNW8AcrOLCCtxbYMzoaTtMcpxmDUWmOBwvoLWvpLYMf2t5wcqUouVJwhDoFhFwwIRdw1C2Iz0THZwKOui9yimJ9imJw1C0Iw2MThkdw9P0zDwHWQYDhHybzLvD9AKZ4hTeb3Wy73cMUgx/KDEJr/Wn0ct8sFis9ny/BMPvQvScuHybtcaMquQAAAABJRU5ErkJggg==",
    "icon_bicycle":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABkElEQVQ4jZWR/3GCMBTH2YARGMEFVARsI2IkJSZFRWiq+Pt0BEZwBEfoCIzgCIzACOk9Gjz/6LWSu++99/3k5UtyaNof63A8+YfjKYOqNV27/VHf7Y+yVuOA7e6grzc7WatxwCrd5Kt0U6brbZaut82eIMTyLD5XspJYXhodjhNhxIko40TIOBE3Vb/iROhPBcyjOJ9HsYwWyRX8Iv4wFCtm88X/IdPpXILCcHZ+5LNZZD4VwHmYcx5KEONhwXhoAmc8NBgPswcZ90OUMpNSlimZE/Zu0AmHvqCUSUrZmVJWVn7Cc8XBtzTff0sICSQhwU1JAoNgQoILIUGplAfBpHoCVPCEBIWGsV/iMcnq20APrOqxXygvMfarp9znsG8C1zwPS8/D903ogQ2HI9/zcDkajXU103oMqOc0hNwSIfd+A+gVOw8Gw4oj5BYIuTlCbvUEqMoXmuO8JJblSMuybz9yJLDHr/X7ry3bdkrLcopez/6CCh54NdDpmGa73b12OmYG/W+/t9vtGbBfz4EH/g38us/tOlMULgAAAABJRU5ErkJggg==",
    "icon_bug":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABfUlEQVQ4jY2S7a2CMBSGuwEjOIL/zU0I0XuJYgUlGLkolVpoIBBGYARGcARGYARGcARG6M3R+nHxs8kTTjnP2x89RUiuNMsL9OF66MZJVsdJqpzqVImTtIqTTJxI66sHveyyRxGPj6dFPN5HPCayziMeiw657BFwL1kW8mbHoh4LOWEhb3cs6rOQVyzkokMhey24MtOggLIyoKyiu1AJKGsCytqAsjqgTHSoZa+RbgVZRLZUJVsqfBJUPgn6ZEtL2D+hBAdcuVeP97DeEOKt/VZSeWtfPKE6e5D5N4Vfb9NzXa92XU+8oQb34Xyd5cpcLlfiFeDcBW3bUWzbqWzbER8C7vHNINOcK5a1OFjWop3P7cKyFuIV0mkhA1mEsZljbB5mM0uZYrPA2BSvAAdcyEAWTSbTxjCwOplMAWEYeA/fR9z0VJlpkK6Pj89S18flTb3X9bHocNsrz/XlIjVt2IxGP5fxDIffpaYNBQD1+T844N5NYjD4up72Zt26f0VoUI7TROi5AAAAAElFTkSuQmCC",
    "icon_calculator":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAyklEQVQ4jZXTawqCQBSGYXfSPgZB+mGFF6xMsbTCMPKKS5qltASXdOITi+jQ4Aw88IGH95+GMb2m7WXb9TQHbo3vV9Xtoqo70mH8vkdZE5RVY6m871iguD8I2Ie5d/mtoMmQ34rnH8P7jgUu15x0sECaXQiy81WCagMLHI8pQZKcJKg2sEAUJ6SDBcIwotEhliPVDiMe2G73BEGwk6DawAKeH5AOFnAcj8B1fQmqDSywWm0IbHstQbWBBSxrSTpYQAhTCmHSTJ/f+QU7DFxI6gm3lwAAAABJRU5ErkJggg==",
    "icon_calendar":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAv0lEQVQ4jaWM4QqCMBSF7xv0CD3IEH9EaImIGIammGOmDcVH3SPduLHtR0i2PPCxwz07B0BrnOb9OM1IwILW8reeckICXPJ+kKofJPaD9PX76ZduxivoHgMSouuTJb+WQ8sFalTLRdJy0Whv7l9zaO4ctwBV3eAWoCgrJMpb7btgepBfCyTAUbaXXXIkXAdsL00zJFwHbC+OEyRcB2wvimIkXAdsLwzPSATBafdrmf6aHhwOR9wCMOYpxjz8E/UC/5I3ajUWudwAAAAASUVORK5CYII=",
    "icon_car_dark":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA7klEQVQ4ja2S7a3CIBSGu4Gj3BFM9IfR2rSxpsYKgQu3FcToCIzkCIzgKB3hmKOVXD9pjG/y/CHPeYFAFH0zG7NLN2ZnA6RPh5U2faUNKG2OSm/da85O/6GgqpWr19qFTokOujeLQlY/QlYg/+rH5rugg66Q1cVlXPQ4Fwf+K4O7X4Mu58LhbEQoawhlQChzhDLbEdfONFG5orYsCXzEitrzkYrFEorFsmmBAN7zd8rnBeTzgrVAAO/5giybQZbNmhYI4D1fkCQpfIIviOOETSZTQOI4ce/45+1v3nY0GgMS+gMvvcFgaJFQQVevc06AWg5xAelpbgAAAABJRU5ErkJggg==",
    "icon_check":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABH0lEQVQ4jZ2S64mDQBhF7cASUoL/w0JQNq6og6KrjI/ER9RRWbGELSElpARL2BIswRIs4VsMbHxgou6F82M+5swM3KGojfkqyh3132R5wWR5AVleeJvlhGQMSfOWpDl0JCT7Xi1HMaGjmDRxksKQKCa3RTkILnQQRnUQRjBDvXiA54eV54cwQ+MHF/qx0XZOnu2cmKHsuOeb455hhtY9ef1ejG3GshzowNgu7zPLKf9mU2zb7WXDxLRh4sYwMQz4mawfmCYeV6jpRqXrBqzi07y/bhRV1WpV1WAFzytDSLnKSIFnIKRUi3VJElJEUW5FUYYJtSShvq5XEQRxx/NCfTx+QAfPC40giOvkYViWux4ObMtx76N/sSn7/duqm38BK43Ui5YmqscAAAAASUVORK5CYII=",
    "icon_clock_dark":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABeUlEQVQ4jYVRi22DMBD1BhmBQZI0Ek1EgDopovkDRqYQvk02yAgdpSN4BEZhhKsuAhdIaZ/0dOJ9TsYmpIe8uLC8uIq8uEKPAj0yhCQtlDQryjT7gL9ZlJjtlM9xqpzjtIqTDOIkw3lL0nz0szxXUKs9wCx25IIwisswigFndE6kEUbxF7L5Rq+dvYs8CBkPQuBBWAXvUedoPAhL1NsaZlCrO4wwnwvmc/B9fuvfC+rInqYwn3/WniCOywDpen73YgiR3snxRifHuzguKx2XVa7nzxqPHI4OIH97mcarKY4nVz6j7G13B9juDp3/bIA6cr8/Ppyu7gGx37Zwp72Rz/YfbHujND1iWbawLBssy364xCFgtu4Islq9MkrXQOm6onT9cNQ+MFNnAbsEYZq0NE0KOA3jZXAJeu2sNHTdVJZLo1ouDcCpafpN03S5SNP0EWrtDHY62xcLTVHVeamqc+jyueppJWYH/3E6nbHJ5EmMx1NoEzX0+vlvDtAHLCkegrgAAAAASUVORK5CYII=",
    "icon_cmpt":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAACXBIWXMAAAsSAAALEgHS3X78AAAAhUlEQVQokZ2SwQ2AIAxF30iOwITcXIohYAdvnmqgiohgEJLfhtBHWygiwoxIpl6WBYtJHgZADQ5YpFD4BhUSVgSH4E8f9zaG9cGQgjaEvZLCoSxbjfakGVqgy2UvNahl+g7oM2j6Gfc/Gad7HHhV4nkTvOHXP15QH7wveExOuR7g9KzO6AAuen3DA4RHKQAAAABJRU5ErkJggg==",
    "icon_coffee_cup":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA0ElEQVQ4jZXS2wmDMBSA4WzQUZzAy4MtogQJSlAsVvESrcUVMoIjOEJHyAgdpSOc0qcqNSYe+N5yfkIIQou5D+NreIyw53sGbU3XD3PXD6BpXi23rJ9b1sNBv0jdsKlumDhoWt2iKCujKCuhyfh7g6KsTvmtBE325kNm1xx0INmkaQY6pAFKE0FpAgpvaSCKqYhiCgpCGiAkehISgYI8gHHIMQ5BYf0L0WKCAPMgwKDApQHP87nn+aAgD7juJXTdMyjIA5blGKZpwx7LcsLlzgeRzk/BnjLgpgAAAABJRU5ErkJggg==",
    "icon_coffee_mug":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA2klEQVQ4jaXTbwqCMBQA8N3Ao3gA6YNIYDWbOmYl1jRN+0PaDTxSR+kIO4JHeLHIwA+iswc/9h7bHgz2EPo37uWjupePWkHVaXC9laCq06A4X0FVXlyqvLhonwbZqYCJmjTLdZQkKUwg5BonqUD7QwyqeHzU2hyFYQSq5NPDMHp98mCzE8FmBwoEC7ZaWyNK2ZNSBmP5lAnpWwtEiMcJ8WCCxnV9HTkO0TBeNxivYYQGO6TGDqnkvd9nWixW3LaXMESe650Jy5pz07Sgj9wfHCzDmNV91Md0ZLwBnUR2u2GO4W0AAAAASUVORK5CYII=",
    "icon_construction":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAmklEQVQ4jWNgwAGyc/Ln5+Tm/4fifgZSQGZWDn9mVu5/ZEySAWnpmfZp6Zn/0bA/w9AB8QlJ/7FhojRHx8TZR8fE/ceB7RkGPwgODv1PAPPj1BwQEGQfEBD0nwDGnR58ff3rfX39/xPAuJO1l5fPfi8vn/8E8HmcBri7e953d/f8TwDfR9Fkb+/gb2/vWE8edvBnsLKy+U8JBgBXq8IH7m3jQAAAAABJRU5ErkJggg==",
    "icon_construction_hat":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA0klEQVQ4jd3SwQ2CMBQG4G7ACI7A/eVFAY8NETGCJGJVVEAgdQNGYARGcJSO4AiOUGNEjFEjvRlf8l3a/n/ykhLyn5MXXMsLzvLiUN5wnhdc7xSOk32VpJl8J04ysYvTwcfwahXp0WYnv1lH2/ptwTxkIlwsZRfzkJVPYc8PRr4fSAXnqTfT2gLHcevxeCJVOI7L2gJK7YpSW1BqSwUlQez3DMMSpjmU6qyaAOAJAGXjCIAcAAcA+NiPkOs7rTlnAFgD4BkAxf2y2yd5LeSquR+cC0omx3qsf7toAAAAAElFTkSuQmCC",
    "icon_cool":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAB5ElEQVQ4jX1Si42jMBClA0qghOtgdVltLut1zgFMQBYEx4EFHKJQwpawJaSELcEluARKoASfxuegZJW7Jz0x8+bN+IfnPcCxP/vH/hz0p7MCQgya9y90svc72Q8uDjp5Gjp5mjp5Gh0hHqDmPJtO9j/mAW139JtW6qaVqmmlaVoZNK28uBh4AV/Tyq8bz+ZuF1XdDPV7a6q6UVetfm818H+eGeJQf4pDPQhRaSEqu6IQlQK6mAtRGes51F/iUNvjeCUXfsmFPT9gLyrIdcnFpeRCOfKSC8P3B371QQ/0esWOB3lRTnlR2lUBu3Lv50Wp86I0rmaKHZ+bwQs69HqM5YqxfGQsN4zl2uXKxcZxeqBDj/KyjKk0Y2OaMZNmTEPutMlplje6dtoIuUfpNqBJOiXbbD4CpVtOk9SATpNUO8518Noa3QZg9uM4GcIwtrcahjGPImriOIGvAoIniqiOImqHgBd6QPeuICQcCQkVIaEhJLQX5nL7jJtN5BMS6hvP32f0HPCafOA1MXhN5p8Er4kGzjn+PXz3WCCEA4SwQQh/IITHt7d18Pr6dnGagdj5PhHCA0JYw/duyGqF5i29vPwalsvVtFyuRscJtBuvD7wbcIvF4tlfLJ6Dp6efCggxaI+8fwCCnSjFiWTX/AAAAABJRU5ErkJggg==",
    "icon_cursor":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABOUlEQVQ4jZ2Ti22DMBCG2SAjZIROgFCVWFDAPAKxICRQC8SjoHSEG6EjdISOwAgZgREywlU0TRMUHkl/6ZPs39Lv0/ksCIIglNUeymp/eCv3T8J/lBcV5EWFJ0rIi3L2UECaFZBmBV7RpFkh3R0QJynESYo9fMZJOl0N5zFwHuMAR85jczQgjDiEEccJ6l34Ou8NCLYhBNsQ7+C4CXbvNwG+H4DvB/gAB8/bXKphzAPGPOxjzbzp13BcBo7L8Ir6b+2s68kA23bAth38pVmt3JltO/XZs6xVNBpAqQmUmthiGNZPyYZhzc8epeaRUnN4HjSNgqZR1HTjo+Prxsk/0TnrSFFUUBS1UVW9c0u7b31FUbFFll/6PxshckSI3NttQmRzuSTYsliQr9FeDEkUpVoUpUaSnm9G+hvkoeKfBNBUYQAAAABJRU5ErkJggg==",
    "icon_cut":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABUklEQVQ4jZWRjW3CMBCFvQEjMAIDBFqJRFVEYmwFBDJBmPwrNG1HyAiMwAiMwAiM0BEywlWHLgjq8tOTPuXuvZeL5TBGVX18vb5XnzV7UJjBrGGUm0qXmwrKTdW99TJ6lBGGmRdlnRcl5EV5uLUAPcqYJ02zQqRZAUiS5sYXUGt9zBoL4iTrRnEKxHcUJZ3Ww/6kkR8n2dm7Kr2Oa72OAVnpaNvq2Lc6Zti9CperY7hcAdEj2vnIHtVisewpFTZKhaBUeCCwb9Bjz9R8rvRsruAS1Nh/ajKdbSfTGRDn+7hbUgYdKQMtZVBLGeylDIDYk4be33/A50JwLhrOBVxwJC61BrPGAs/jDeL7Y+35Y+F5HDyP7wlA7eRRzljguiNw3dGOek1zTWB/ukTM4GwssG2nGQ4Re4dP23bAcd66CPa/PPME/f6LtqxBY1kDwCfOz3g/v6Dh0zFWMi0AAAAASUVORK5CYII=",
    "icon_dashboard":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABuklEQVQ4jXWRfXKqMBTFswOXwBL83/ZNLe+1WEYkzwyUiCVA+RCLzyW4FJfgErIEltAlsIS8ORhbRXtn7iRzzu/ckEBIrz7qf6LebGW92apeS3jkp6rWtVGt66Zab5Ru7KXuMx1MbVyEi7IyirJqi7JSRVk1RVl1JxVltUPrvdCe0uz3kCwvmywvVV6s9nmxGmZ52ULPi5WL1kwLDwxYZLpwkmYiSTOVpFmTJO9DaOl73q3nddLAdOwxI4iIUyniVIk4FSJO20gkw0gkBtb+EGhgNIuMJOEyUuEyOn6OrrcoHoTL6HMRvg1+enRkkCWch4rzUAbBYhcEi4cTwHm45zw89INgwCKDLPH9QHl+cPBf+c5/5V8DsNde94gXOlg/kPAJY55izLu4wqkY8z4Z81rGPOOG1yBLKJ1LSufKdf9eQZTOd/AonW/PdbBal8RxXOE4rnIcV/YHzGZ0MJvRq78BVmdEJ9j2tLHtqbLt6f7WVc4LjGa/rz2Z2IZlvbSW9aKenyfy6cm6ug40eGDAInMFmOaf5vHxtzq22YzHphyPzQP2Jx3MrQO+6u7ulxiN7uVodK96LeH1+f/qCwR3t4HC8gAAAABJRU5ErkJggg==",
    "icon_delete":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA0ElEQVQ4jZ2RawuCQBBF94dZfdBCLFMURVG8rJqPDP//t4nNkh67ag4cloUzl90Zxp517Xp0t57EyRSldJq2Q9N29MZPiNKp6hZV3ZKEMWTSKcqKVOTFBYIph/G8BOcFrSIvh1dm4MjA6U8+55SkGZI0o4XINxXHCeI4oRmUa2ZBGCEMI5pCONJm3w/g+wEt5DPEdT24rkd/MoScbAe27dAaRC87Hm1ScjrjwYTDTNOCaVokYfznrGMYB+j6nl6I+/eQZ53NZgdN25I4VWuWOXcxyHEMjvuNcAAAAABJRU5ErkJggg==",
    "icon_delivery_truck":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA/ElEQVQ4jbXS3W3CMBSG4bMBI3gE7iOiXEGrJOZHJI1MHOzEhaqloG7gERilI3SEjuARMsKpjJwKqYGaSn2lR5HOd+OLAPxX+8Ob9gF97V4P5GW3Rx9wqe3TM/qArkZtSKM22onU4xZ9gE3IZihl08paGUfLWqEPKPl6yCvR8kp8rkU94JXQDvoAxsqWrfj7qqwG9jWMldpBH5DlBS6zB93J8uIjywv7RR+wWCyxh75w/wEoneHJdH5M6UxbdDqPvu/9+7G7Q5JQnSRUxHFq4jhFx9ib267uYJtM7sl4fIfnzn+q3/ZTYRiZMIzQMbfuEAQjEgQj7ZBb9z/3BaoASneUcIc+AAAAAElFTkSuQmCC",
    "icon_dlvr":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAPCAYAAAACsSQRAAAACXBIWXMAAAsSAAALEgHS3X78AAAAYUlEQVQ4jdXSMQrAIAyF4RzNOTlrxd1oerPXoRQ6qA0EhA7/mG94hABQNPoPoloRRlgEra4hF8If0PSIB3VVhBEWgfWGEGI3kDybpHcPcJoNAfewR85TwIWUUpbAvo/dhlzGet6GGF1oigAAAABJRU5ErkJggg==",
    "icon_email2":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAw0lEQVQ4jcXT3wmDMBAG8FtN2wcpUimi9U/SRGOVCJIRHKEjdYSO4Ag3wpWIBSktpfpg4Afhu+8eD2Dzp9sOddvRQgh1o7FuNC2EUF0boaoaVVXTn9DugpQlClkaWaheFgploegH2+nHHVkiMC5oMjAuDL/InnGBs/wFp5mZumMOWcZoLs3YkKa5yXJu3SfGZnb23of4nNJHcTJEcXKz7P9bD8IwojUgCE60Bvj+kdYAzzvQGuC6+4fj7GgJu7v1KQI8AbeCeo6eiycLAAAAAElFTkSuQmCC",
    "icon_email_open":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA30lEQVQ4jaWMawqCUBBGZwctoSW0ATGQfkQhZTfNwcIKzQdeXIJLaAktxSW0FJcwMT1MSiN14MDcO9/5AGomkekgkWmWyDR/wvsAmiaKk3GFLIplEcWSPiget3e2LAjCmLpwlz0/cP1T+Hi0GHbYhcPRI6ZtQem5+yMxbQtKb7tz8+3ObV3ADruA6BCikyM6o39lRGf4dAisDdIL07IvpmUPm0S+cabqgFhb9IUwL0KYZRHv97+aLBiGoCaWy9WV+ZUBXV9QH2A+16kPMJ3OqA+gaRPqAyiKelYUNe/I+QZQ+kUStq4EbgAAAABJRU5ErkJggg==",
    "icon_exchange":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABAklEQVQ4jb2Q222DMBhG2YARGIEFIugDRSXEcYvBxDG3Qk2hoe1IGSUjeBSP4MpS1IRIhoaHHuk8Wd+x9BvGfzJ8fvPD8GUtDvQfg+z6QXT9wb5ryNrOVbbvvVSythOs7aYjdcPMumHH5q2VOuuGldpAVdWn6rWRcxrX0Kwws7zkNCusLC/ljCIvKvd3TAi1CaGcEDquXqHezor9PrvcIME7G+OdwCmRSl3g/M7TlFzGURS7EUoEQomcNMYWQgmPk9QcVSF8kX/wpL02ALDcACh1AgCP2+3z+Ndb1uuNHQShCIJQKsMQuMrJ0S2+/2R7ni8871F7xFkc58FarRy+OLCEH+QXuNyCMObRAAAAAElFTkSuQmCC",
    "icon_expand":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA0ElEQVQ4jcWSTQqDMBCFvYFH8QLSjbZoYypBcaWG1J/UVnoVj5SjeASPMGUWQhGNsZs++GDImzcwQyxLo1f/Voj1ix5dP3TPHhCsD4Vb2fFWdrCAG4WrunXqRk51I2HBhJ42LERlC1GN4l7DKuiJyt4cUHKhSi5gh/Wj5gV38oIrQ/Sr/EdJmjlJmilD1ldgLFGMJbDD9s+MY2ZTGo+UxrDBiD3aVaLo5hBCJ0IoLJjQM7pHGBIeBFf4Bt+MwrN8/zJ43hkQrA+FZ7nuSSG6ng+z+7zVsUCHDQAAAABJRU5ErkJggg==",
    "icon_fan":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABaklEQVQ4jY2S8Y2CMBTGu4Ej3Aj8T/UMkguiRyDCVZ4FixiVKL3eBozgCI7gCIzACIzACL3gaYIXUF/yS9N+3/f+eH0ItVTKhZJykaVcnFP+k6dcHFMuhuiV2h/4aX/4lu3w08PwLtlnu2QvnyA6G2y2SbnZJvIJWWeDeL2RL9A9CxbFOYti2UIZRfFxtVq/PZxBuIyGQchkk3AZXQZHgyULQpYHIavqkwZL+xICoAoAPQPQHICyxSIYAtAKgMorNgAtGvcmDBHil2QO8sYX8Y++v+jN58DIHEpC/Kqp30H8CrkekS0Urkdy1yOV6xFxvbf5JHKcmXxC5jgzu0tHlmVXlmXLB2SWZdsdWommUyubTD7lA2q91VNnkWlOe4ZhFoZhyjbG44liGGbeolV19vKVuv7R0zS90DRdNhmN9MsOaJrO/mmVrn8od0vU77/3MB4IVe3nqto/YTz4W5RrYTxgGA+y2lN7b++/xoZoobbqQk8AAAAASUVORK5CYII=",
    "icon_favorite":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA5klEQVQ4jaXT8QmCQBQG8LeBIzRCC0giQZYomqZohiKVcnbkCI3iKI7QKI7w4oGKRR6WH/zguO+9/+4A2tz4fXnjd6UldfeDXhr0y75gBZdYwWtWcPzwGMw8vvS0I0GWsyrLGY4oW2N9BZdrjgJNa3QG0vSMc0CcpDgHRKf4GZ1i/NMTwjBKguCI/6BdoHh+UHt+gD+q+7fgHvyF43qN43o4UUM7by/Ntp3EsvY4Bc3Ct5imVRqmhSI0A6LoulHpuoEjKuFyF03blZvNFoc0bdf/jUlR1XWiKGpD6PzTchdZXi2IaOYFLoxs3pQnVR4AAAAASUVORK5CYII=",
    "icon_fin":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAcAAAAICAYAAAA1BOUGAAAACXBIWXMAAAsSAAALEgHS3X78AAAAdklEQVQImVWPwQnEMAwEU8KVlBJSwBrsl22wwe7gOrhSroQrIaWkBB1jokcEYtmZj7Rt90h6SdpJZy4+kiylZCTdxTvGaGMMm3OupMORV+99CV86HPkQvnDkWUp5iFor8kQeIQTLOVtrbSUd7kfxwlfS784d/gcntF+WVPM/vwAAAABJRU5ErkJggg==",
    "icon_financial":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABK0lEQVQ4jZ2R6W2DQBCF6SAlUEL+W5Gw8ofDoCUmEFiOFTYGYWG5BJdACZSQEijBJVDCljDROhBtvOaQn/RJ80YzT3tI0oSq0xkY0jMqj5VcHk/wSyUvWsqLUs6LssmLEkb4ZjMPl/dZLmeHgmaHAnquXM1D91n+IgSku+yS7jLo6fre4BWuZpyFgISkl4SkwEGGetH9o5goYZTAI3AYNziMCQ5j8ei8MI5QEIRdEIQwhu/jWpqT9xUgz/Nr1/NhhPkQJsdx4canRxzHpX/eccV3se1tO4DQx+2VbXsLjL6uBz/0/sm0UGtaCHqoaSGF87JpoY7zrRCw2VivhmFSwzBhBspmhQAmTTNkVdUbVdWvqqrDHaxXa5ox/ZW81ut3YCxeuNdq9QaMqZkf1Unu9Y8Dq28AAAAASUVORK5CYII=",
    "icon_first_aid_box":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAyElEQVQ4jbXTSwqDMBAG4NzAE8mspIiKwSc+sShKrNYjeLQewSNNGehCJAmiNPCRMPwzi4Qw9o/1mt7rNC+4R7VTzWKcDDHOKMb5I8Z5/aEznhrQDwL6QSDtu9pKNWlD2/Vb2/V40caaZ4t3sKpu8A6W5yWqFGUNeVEtugxL0gxV6I6SNANtJowSPIriFAgNiOLUoHMYJYssyzgP8Ej2WpwHIM26no8q1Oh6Pmgztu2gCg2wbQe0Gct64B3MNGEzTcCLtlP/Q7e+6TVkH9zTV0MAAAAASUVORK5CYII=",
    "icon_flag":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABOklEQVQ4jZ2RYW6CQBCFuYFH4Aj+JyZG26glIlQiEVgchIXt4q57hD0CR+AIHoEjeASOwBG2MbVNbWtVXvJldubHy5sdjXFRMy4k4+LAuGhO/Y7t5Y7txY7th9ot0YJLWrCWFhxowdVv2JEWrH/VgLwVek6oygkVOaHt+f2T0/x6GpyRCmekwRmROCPqBnWK8yrFuUxx/pEsSTN9m2C1TbA413s5fKWAOKk3sK0hTiqIE3UH5cUaKIJhiDYqRBv7XD9pUQQlikCiCA4oghpFYP/5F74fHn0/rPwAlX6A6iBAoD0iz1uD563VylvrWle57qpx3dXlfo/IcZbCcZatbb/2OhksFk7PsuzWsmzZOYVpzkvTnDedDWYzU59OX9RkMnvsCt81Hj9Xo9FT9xSGMegbxkAZxuDfk74DI+7Lc3MZy8AAAAAASUVORK5CYII=",
    "icon_flash":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA90lEQVQ4jZWS0Y2CQBBAtwNLoAQLMCfiXYKCy6IEXMAFNiiCJFLClWAJlkAJV8KVYAmUMBcTLyEr6PKS9zkvmckgJHAqz8qpPINgg2TJi7LKixIEL9KBQ5bX2bEAQUU6kO4zELxKDyc8JQlPoS3nqSodYFFyiWIOLW8sStQOR52BIGS3IGTwxt8di58DlAYKpQG8sfH9cNy7wnbrq21dj367HoV/PY8SNISN49aO48JD+V+4Q8h6ZNsbePiDhrLCJMaYAMaksSy7++qvMIxVbZoYTBP3H60PXV8qur6ExcKoBg/f0bTPaj7/kn9hkcnk4zqdzqT2/gPX+aX3PaYgBwAAAABJRU5ErkJggg==",
    "icon_gift":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA2ElEQVQ4jc2N7QnCMBCGbxP3KIWKf0RR/KUoirW1TbyY6AiO4igdISM4Qkc4OT+gtFfMTw8eCO9z7wWgMWd7Sa271tZdid+tnNg1886gsTUaV6FxdzSO0NjkDb9fWcU7vQeURlIaH0rjTWmslUb/of5k7Kj3QKlOSVFqX5SaevC80ylmeeGzvKA2+bFMGMlx51VOD/lgn2Yk8f3gl4ftbk8SoR42my1JhHpYrtYkEer/YGbzBUmEephOZyQR6mE8npBEqIfhcEQSoR6iKPZRFFObhu847rB7AggWOBopb4W3AAAAAElFTkSuQmCC",
    "icon_gift_card":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAw0lEQVQ4jaXObQqCQBAG4LmBB5JI+iOJkWhGYhiStu262hH2KB5lj+ARPIJHmLCW6Ms/zsADs++wwwC8VSUbq5LNrZKNGvuvXJnZK/8pLqTmokYu6oEL2XEhLaN7ZuNM6skFF8bxwnjLrmJpemWgydqxn1xQlKwrSoZFyQYD/7w/L8jzs6KA7JQjBaTHDCkgSdI+SVI9Uw/x/qBgZj3+hlGsw3CnZoliDUEQIgX4my1SgOf5SAGuu0YKcJwVUoBtLxTFHegGhSbdifU5AAAAAElFTkSuQmCC",
    "icon_go_to_bottom":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAxklEQVQ4jZ3QXQqEIBQFYHfSUiSil0Fq+plCiqSoLIq2cJc2S2kpdxBmIO6EWBe+Fz0eVMZOZlk3WNYNCWCuM80rTPOKhHvBqGcY9YyEe0E/aOgHjYR7Qdv10HY9Eu4FjWqhUS0S7gVV3UBVN0jYC6Ss3ge7lBUS+zHzV1CWUhWlRBcme3qL/FWqLC/QxmSsT0nTXCVJhmfMntMnxnGiouiJR2aNXRkhIiVEhF/XDv/m8RCxYQ0FQegFQchv8hjnPnDu403wAUqz4W+nZiOCAAAAAElFTkSuQmCC",
    "icon_go_to_top":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAwklEQVQ4jZ3P3QmDMBSG4WziKMELkaCkSiQSFEOqVfxd4YzWURzlFC8KbWpt6gcP5CJ5IWScFhinBU8C0g+z1w8zPckjR2u7/rIhZ1Y3rW5uHW6281+Pjam1uTb4xtRukUobXWmDXxxHirLSRVnhD/sRpQqtVIGOPiN5ru5PMlerzBVa1tc7h18RmQSRSbQAcV2aCkhTgRb3AOcJcJ6gxT0QxxzimKPFPcBYBIxFaHEPBEEIQRCixT1AqQ+U+mjZDTwAbQPqD+QJkeIAAAAASUVORK5CYII=",
    "icon_gym":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAnUlEQVQ4jd2PQQrDIBBFvYlH6CVCEWkooSgONqSlCYZcIkfLkTzCFBdTQnAGumwH3uKPj68q9T+T5kWnecHC1+fjlPQ4JSS4S0Tn8XwhwRWIzr0fkOAKqg5AzABxA4i4Yz3k2q7krJwP2fmwOR9wx3rItV3J+fOSrrshwX1BdNr2igRXIDrWXpDgCkTHGHtqmjMWuAI6N8ZqzvnBeQPXApwOtrG2aQAAAABJRU5ErkJggg==",
    "icon_hammer":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABNklEQVQ4jZWTi23CMBCGvUFG6AheIKLioQZIDIZAwHk0j/IIeZARGIERMgIjdBRGuBGucuVWqNA2+aVPdz75P0v2mZBfVJSVVpTV6YaqKKsn0lR5cdTy4vic5cdzlpcoOWQlHLKSkrbap9lln2aogN3+0K7JdpdW212KN1xbNYiTzSl52+ItcbKp4mTz/52EYVyHUYKSKEpkDl9rmZO/5Adh7QchSoLXqFa155+1OwnhaUJ4tRAefuL63xtdL9CE61+E65/vnYSQpbOmjrO+OiuBktVKPD7lkWx7Se2FA/bCQcV7YzPnc8r5HDifowJmM7vZe1tsShmbAmNTVMBkwpuZx2OLmiYD02SoAMuaNJ80wxiBYYxQAcPhuN2Y9np96Hb7KONg8NL+o+h6h+p65yRjazMh5ANZ2qQVA87NegAAAABJRU5ErkJggg==",
    "icon_hand":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABOUlEQVQ4jY2T8Y2CMBjF2YARHOEGIIYIf+gRCQjSw1PhChWo9GQERrgRGMERHMERHIERvktNvcCJ1Zf88l5T+viSgqJIVLJDzL4rKNnhTXlVBWVxQdmZZ7pnNd0z4F7QclRQ1vJ9aUGW0zrLKWQ51TuZeyVyJS0gu7wmuxyEd3Mjsp6STE1JNjwJTkiMEwI4ISeckFrkGuP0wvP1GZweeU7SnXpXEMVYj2IMguafn7fR122/GZxgs41H600EgraTOScBz87foTD8PAp0vl6t1vCA9ua9tyIUtgiFwAlQ+INQeLmtH9Affxl8jHw/OPt+AC9yfwOet1Rd12td14NnLBb+8Jdp245j2w48Q5HJsuYny5qDDGnBbGbp0+k7yJAWcBmGeZlMTBjCMMzrjyaVpo0rTRvDA3pX+AtXsiA53tTF8gAAAABJRU5ErkJggg==",
    "icon_hand_pointer":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABDUlEQVQ4jZ2R4W2CQBiG2cARHMEFtPyhRgu5qhAJ5Midp9iTE+sGHaEjOIIj3AiMwAgd4Wu+BghUrJQ3efLe5fI9348zjJYc0/P7MT0DttEniUoviTpBok4fvQTyoLQ8KHiTybWXIN5LHe8lYPcSiG2sxTaGWmcbsRtsxG7UScC50JwLqHV1Zly8Mi6GjQEasQGNmIkUd00jBjRiedFIVjS+feFMJQhDaoYhBSQIaY6U99/U3n6WVfH94OL7AfyDpgDjeuvM9dbQkVvBauWZy6ULHbkVYAhZ5IQsoAPtAtshn7ZD4BGOQ5pfWWY+t0ez2Qs8IG8dLmNZ06tlPcN9puxPwWRiDsfjJ7hDY/s3Ne8CaPgEtK8AAAAASUVORK5CYII=",
    "icon_help":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABJUlEQVQ4jZ2SgW2DMBAA2aAjMAIjQBShhAaRNoIaEyjEMXZNTBiho2SEjMAIjMAIjODKEWkRCtBw0sn6t//1sq0oPU78/HLi5wvPi4rnRc3zQkhlTu4pU7CMlyzLtb84v7KMi9ZytJhQphHKakJZQyi7HSaU6YQy0VEdbJCSLw2nVNyVOZxStZvDKdVHp0DH9HJAWCCEbxMcEI5lfBcd0+EJHhEnqIoTJFrH76BPGMVFGMWitYk+k9/LnQTCvQqDsIFBKGAQ1sE++n+xBABYAAAFALDy/WD6/fu4HihdD9Teh/98sWS3c7+lyly223fVcd6usxvYtqPatqPLdVYDy9o0lrURcl2vX59rYpor3TRXouP4932EYSwqXV8Iw1jUy6U5+BI/7aKNhM/ChwsAAAAASUVORK5CYII=",
    "icon_hld":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAHCAYAAADAp4fuAAAACXBIWXMAAAsSAAALEgHS3X78AAAANElEQVQImW2KyQkAQAyEUkOO/kt1mccEFvIQRIyqQgBhX/liZiIU7fd5xu5GKNpjZhCK9gew7jckKp48xAAAAABJRU5ErkJggg==",
    "icon_hot":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABT0lEQVQ4jZ2T4Y2CQBCF7YASKMH/Ro9EQUG41c0SEA6ziCAcCHgVUIIlXAmWYAmUQAmUMBcIJkRE726SL5m8nTe72Z0dDHoiTr7YODmlx/hUHuM0Hfw3wii5hlECYRRnfzb7Qcj4QVgEnxFU+EHI/trsej7rev7FOwTQgntp3Dkuu3Pcb2fvwT179zB8aqa2w1LbKW3bgQcUTQ1X1T1sYG1pZm0p9FCtcdaWlr0nME0rNU0LHmGY1rWizo0PpmPWdIPdbExG141C1w14warTgKhaSlRtSFSNElWDF3RnAmOSYUxyjEmBMYGGspW36TZAaE0RWkOLC0Lr8512ozsPyvuKkRVUygqChnoXRUHnllaR976CJMkrUVxCw/Wmi+Ly3GiFJMnPx3k+F4c8Py94XoDplK9vezYTckFYZIuF1H2+vphMODoev+Wj0fjpV/4BosDrRj0Bb1EAAAAASUVORK5CYII=",
    "icon_hourglass":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABL0lEQVQ4jY1S7YmDQBTcDlKKFYgQE1jUbPyKoqenp5iIH7l0YCmWYikpYUt4xxMveIdrHBjeY2Z2fiyPkAlN+71r2gdv2ge8ISdLqJv7rqpbqOr2WdX3YZnotUBEuJUV3MqqW/E7zAgLimsJxbXsV/weM8KCLC94lheQ5cUwzTl/teU/QKRfuZKmGU/TDATkmCFriD9TKYoTHsUJTPO1o0e2IPyIpTCMeDARd9TIVnh+IPl+wOdEbdNjx/Ukx/W4e/HBvfjdREANvdXHpmkrluVwy3LAtt3XPeCOGnqYERYwZnLGTDifreS/hxp6mBEW6AYD3WDjIen6KdENNozUT2MhepgRFlCqAaVaT6n2nPY5UUNPXHA4HEFVj8N+r3ZLRA8zwgJZVrgsK/CGf/7gB7o37CJqbnfJAAAAAElFTkSuQmCC",
    "icon_ip":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAACXBIWXMAAAsSAAALEgHS3X78AAAAkklEQVQYlXWQwQ2DMAxF3wAcGIhDRmCUTmLUqkckJqgYod2EG1dGcPVTgyxEI/3o5/sltoK7I2EUjAnjHZqUHfWABgzH2BK4RTZUBqOPYMZoU4c2MtV64vaSoRO8VCY/f6VjLG3Ns/HyKpdSbQfXah5/9Ou4CrzFwbknQH7PxcQcYwrPGtFKQ3cYn/g/Sb6rEPAF/cmo6ERE7E4AAAAASUVORK5CYII=",
    "icon_key":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA80lEQVQ4jZXTW46CMBSA4e7ApfhuJkF9MKPC0CnQqaBWvAxIICyBJbgUlzBLYQku4ZiampByaedPvqSEnD6UgpBBeVGO86KsGsbItGuW365ZAW35TTucpFmZpBkoakmsy8ENzpekvvymoLAkEO9RX3F8GsXHM3Sopdcz6usQn0b8cAQd1FcY7Xi03YNG3TnMWMg3mwi0wm37EAPKeEAZ6FDK2p+REJ97XgAdHp5Pqzc/+GlfJNf95hgTUPxhTO4Yk+GbZ9tf3HZcaHIc945MWi7XfLWyQWE2LFosPkFhPiyyrBlIj+l0/r9h0WTyUUnmv2ijJ/vr6l1ylbaEAAAAAElFTkSuQmCC",
    "icon_light_bulb":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA50lEQVQ4jZXRfQrCIBgGcG+wo3SAiBj90Rc2W2NDarjGxpooO9KO0BE8wo7iEd4QFlTuwx74gejrgyBCPxGy8YRsWiEbLWQDPd3veWgqNReLmktdcwkjtJkZLagevKseHGZ0g5eLsmJFWYEjZhXc80Ld8wIcKauAZbliWQ6O7IJbytQtZeDILqD02lJ6BUetVZAkdB0nFFyY2cGfuESxukQxzLCf/04YRh4hYUdICCM6M4OmEgRnD+NAYRzAlxN5mjPkmuMRq0/OF9/Zbvd6tzuAYdZ/F/j+Rvv+Bnr/F5gslytlTM28AFLeFXAKbXJpAAAAAElFTkSuQmCC",
    "icon_lock2":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA9UlEQVQ4jZWQbYrDIBCGc4McqdkfoYQG05CQIopBDOZDSI8wR+kReoQcxSP0CFMEwbJNlnXggWFe50FNkp1azFotZrWLWdHj+ir5T02zuU+zwQPufy7rcU71OKPnMU5L6nD9xzw9FKhBV2rQqAZtdzLrs+OnSKlASoVSqm0n23wGhwLRSxC9RNHLL4Gb+exbwLhIGRdPxoVlXCDj4sW42H7x8pn1Z8NfUMqAUoaRhJt0NwrdjWIkQdC0HTRth5EEQV03UNcNRhIEhFyBkCtGEgRlSaAsCUYSBEVxgaK4YCRBkOdnyPMzRhIEWfZTnU4ZxuB23O4bPvlRRCwTK1MAAAAASUVORK5CYII=",
    "icon_login":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABYUlEQVQ4jZVR7Y2CQBSkA0q4Eu4/MSHEH0QE+VgWF1a+xMChxCvhlXAlUIolUIIlWMJelqwXUPHCJJOXNzNvks1K0gCn5gyn5sxmEIb3Un1soD42bAZhVFBWNZRVzcqqbquvozpF7oscjAqKQwnFoWR8Sm8wmcvzAvK8YHze9ywvvh8LHnN/SNIc0mzfptn+874nac6SNG/jJJOHOaGD9IiIxnJEYzuiMdBdcqG7hAl2EY0/eIbuEhAajI4JiYCQ6BaGlL0i9wiJ1DCkIDToD328lXFAOhwQ9g9vwTZUcUBA7NAXeAhfEMJM8Ib84IL84AchfB3onY+3/RMQwiA0kGzbVR3HY47jXV0XpcMnOY4HwmtdF8kvdJAsywbLstvNxpFNy1ZNy+64xoPCe/pGobM+t15b9t0wDBMMw2R8Pn3PAJM5XV+Brq8Yn+8KJnOatgRNW7IZHBcoygIUZcFmEH4BzAQ1bMs49UwAAAAASUVORK5CYII=",
    "icon_logout":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABJ0lEQVQ4jZWR622DMBSFvUFGyAgMEFUo6g8HqGPzCI+C7JjSENJGGYkROkJGYBRGuJUrHBEoTTnSJ/keHx3p2ggN9Hm+wBzQUNXpDHNAQx3KCg5l1ZTHEz1WH+YUXQ5+KzDQP1S8l6BAfUn5tpB50ci8MB8VyLwABdLiQhpcyFbscxD7/GFBl4OfIc24SDMOPeo045c045Pr6CyKk7ROkhT+4BrHr6MifY+iKKnDKIFH7MJY9Au0j5T8IBR+EEKPr47mzvd3t7fRHtJyXd9gzGsZ84Ax7xb0vGDpun7d+VftdzPc7UWpuyCENoTQ0S9st8wkhLZ6JoSCAg1l2y+TL+84hDoOWXZnUIxCm40NGFsNxhbF2DKnUDnFqGC9foY5jApWqyeYwzc+fhhqs4ShlQAAAABJRU5ErkJggg==",
    "icon_martini_glass":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA10lEQVQ4jZ2MbQqCUBBFZwcuxf/2ChKDKPqiKCztqWmmJC2hpbSElvCW0BJagkuYuFAQUabvwIFh5s6lY3Eyj8WJNTUJZHkhs7zghkp6Jz3k532acR2RpW8k+8MlTlKuEhmqIoxiFUYx/1DRP4JwZ8gguskg4g9vuFEd/G1geL4sPV/y0xI7asJ67ZmuuykhZtJhuXIVJF3mi6WC2gWz2VxB7YLxeKqgdsFwOFJQu6DfHyjY+LHbtSe27Vwdp8cQM3aVT5YljFarfRaicxeiwz+8I4Ps6+8BdBPOSdPZcmQAAAAASUVORK5CYII=",
    "icon_microphone":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA9klEQVQ4jZWMa2rDMBCEdYMcQUfIfxMw/RNKkK04ilznQYKDSxrXro/QI/RIOpKPsGWCVUxZB2XgY1+zIwSjz+Zr1rSda9qOBhx2IlS3unW3uqV/uOCA60dNHMEB1fuVOB4+lZdKlpfqbkKd4M/D6nQuKYTJgMPxRL5yjD2sdrsD+cqx3x+l97CyeUE2L6TNCzf0Y7Cbo58MMMb2G2O7rX2bGWOdMZYGHHa4wTMZsF5vvrXOeq2zM+YsM9LfsMMNHvFISaJ/VKLpjkrdQI8ZNxEipVKpVBqvVooAeuyCnsdaLl8JPP3oFccvBJ56iqKFjKIFcXD+XzIr0fUvISryAAAAAElFTkSuQmCC",
    "icon_music":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABU0lEQVQ4jY2S/Y2CMByGu4Ej3AgsAMcfyInUHnJVDFGDIh8CBUboKI7ACB3hRmCEG6GXesb48Tvimzxpwvv2+aMBoRdSsWZUscasWMMr1pxY3X6zupWsbjvwQlEyrSgZL0rWFSXri7KW/yBAQZYXIssL+QICFCRpLpI0lwB9mh27NDvyy0aAgn2ciH2c/MSH9BQf0vaQZCaw4WqHoES7WES7mA89rOrVDkHZbCOx2UaDAtWrHYIShmsRhutBgerVDkEJVqEIVuGgQPVqh6DQRSDoIngSULrUKF3yM4ugUzsExfep8H16J5jPvzrfp/IBcR0Q4nmEePxCr86briXEkwAdct3ZCGMiMCbygasAY3ICeolnnx5yHJc7jisBroLpFGuO4/Y3XT+dYu9cWpbdWZYtHxmPP57+PtueaLY9ebv7aBimpuvvva6/ywu9YZh/9hfyCwgY6K0z1TvKAAAAAElFTkSuQmCC",
    "icon_na":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAcAAAAGCAYAAAAPDoR2AAAACXBIWXMAAAsSAAALEgHS3X78AAAARUlEQVQImWOYMGFCwoQJE/5PmDDhPAMDA8OECRP6ofz5ID5IYD5UYD1M4YQJEwRgkgJQAZDE+wkTJhiAJYiRxG4sPgcBABssUGdLOhEmAAAAAElFTkSuQmCC",
    "icon_office_chair":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA00lEQVQ4jZ3S3Q2CMBQF4G7ACIzgBIQoMSFoQFOBgC2FBoPy54iMwAiOwAjX3AeM0RBrT/I99Pb2PJUQxTRtb7TdfUJEJ3XTm7e6A0R0U11rQNoF5aUay0ulX1DIcixkqVaQiWIlcjmIXMInpQLGxYNxMfIsD3iW24yLgHEBSKkgSRmkKTPnc3rmBs7Q4qMoTqYoTuCXxQJ6ikDB8keiNDQoDe3Z8UgBvc9wh6jG9w8DIrrZ7f0BKS27rme6rgcqvh6v1xvDcbYT+nf2urAse0L/zp4jKqNsSfk7iAAAAABJRU5ErkJggg==",
    "icon_omt":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAACXBIWXMAAAsSAAALEgHS3X78AAABF0lEQVQokZ2SvWqEQBSFjyLptrHKIyypLIKF3YLvIMy+hK0EqzSCVRrBXiSltV3eIZWPICzYCiE3nGFGxuwmxQ5cYa7n4/6cgYjgnoD+7M8BwAlADkABOP4W3ALPAC78h30MAB7/Al+tMEkSyfNclFIShuG3yc8WdsFnAF8AtKgoCrFnnmdJ09StvAPfec+yTIIg0KKqqnawU/noghOT0zRJ3/fi+76Gm6bZYLZtQOWCC5PLsmhR27Za5HmedF2nc5zZgLkLfjA5juNWoa5rLWTrwzDohRnw5IIvTEZRJOu6bnBZlhtsIFp1cMEHAJ8WZmW2zZnjOHb9pM9XPj5Z+EbQqrf/Xg4rs23OzIVx27SKPl8/uXviB53TVY1DanBbAAAAAElFTkSuQmCC",
    "icon_package_box":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA50lEQVQ4jZ3M4WnDMBAF4NukI3iApH2Y/DDBCJuYmBgHB6eyhRI5HiEjdJSM4FE8Qke4oqKW1PTXHXwg3t0T0dNc3S27utvDDePshpHdME6Bf89+52/ov7EXB3sZeGEKFrnDn3JvbNQb+9kbywuPYJn72+j3A92ZOZh0Zz50Z+7vusczn4Xd9HP/XW7POmrPmoUiak4tmlPLQqD62KA+NiwEqqoaVVWzEKgsDyjLAwuBimKPotizECjPd8jzHQuBlMqgVMZCoDRVSFPFQqAk2SJJtiwEiuMN4njDQqD1+u1ltXplCd/9Atf8xj4/JZ6CAAAAAElFTkSuQmCC",
    "icon_phone":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABL0lEQVQ4jZWS242CQBSG6YAStgTfJ4T1xWzMGlBWBG8McwEEQUqgBEuwBEqgBEqwBEo4m9mwu0hGxS/5MsmZ+U/mpihPOKYn9Zie8jTL6zTLoWMl5pRHxEmK4yRr4iSDO5bSYBjFahjFZXRI4JlKH8bDEQ+imgcRtDZBeLjwIKo6tV+vN2FC2IhQ3hDKobWkLPg5J6G86NTFmjNlwdtfeO/5qodJ7WECQuxT3G3uE6ZinxY+Ye/Sc293XrndeSDc7fFN+Cmuu8GuuwHher2V3+w9lraj2iu3sVcuiNFx1o/fto9lLXPry4bWi/IqprmoTXMBrZVhzAvDmA/fxWxmgMRicIPp9BMkyp9KxmTyAT2bwWGBro8rXR9Dx/NLDRDSVIS0EiENENKuCGn/33MA34W8yIwNevEVAAAAAElFTkSuQmCC",
    "icon_puzzle":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABRUlEQVQ4jaWS/22CUBCA3waM0gnkYQMS8iwIPiS26quGHyJPGMERGIERGMERHIERHOEaEOyrlsTWS74/7svdJXc5lPBUSnha8n0GCU+rOkcIoYSnrHatZ7Vr/Snh6Tnhad6IeMfzeMfhm/1LvOPsp2tohty4EoVRfA6jGATym1ykvHUoCLeHINwe/SCq/CCCBzm19VW3Glpv/Gy98eFBMiTGiq0Z+9zAX6h7muaPxYotlgz+Q92L5u8LeAY08+bwDIi6XjGlM+igrmdR18tE1wd1vcsdbHta2vYUarrDOg7NOvcbjkOv34kmE0eyLLuwLPvynm2Y5gR6OKC+IGPzSMYmPMCZkLfyboBhkNIwCPSQGQapRHc3QNcNSdP0UlVHIKJperOzqo4KwZ96V5FlpRgMMNRgrFwPhvEQy7JyxFjJh8NX6Qv+jZxHwC1ufQAAAABJRU5ErkJggg==",
    "icon_rdy":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAACXBIWXMAAAsSAAALEgHS3X78AAAAWUlEQVQYlZWQQQ0AMAgDJwEL52QSJmnOkDQJW5rw4MGDkfQBLRQYIwVgwAxY5rJoAwe4gaNaJRLpwAp41Ha2U7cXLh6cKdE+6lyFUJPFzS9hz7p9zNd7Og9/+vk5mTfYZ0sAAAAASUVORK5CYII=",
    "icon_recd":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAACXBIWXMAAAsSAAALEgHS3X78AAAAnklEQVQokWP48e8fA6n4////DAQVMaSp/2coM/5PUCNIEIYZ2uz+gwBII0yMOI1p6hCNEJo4jQxbi/4zTPUhQ2MaxDaYRjie4Q8WAvsDRQKKcQGGVIjtkFBblfqfYXUqXg3YNU71gWCIIF7AkEZVjWnkOHUKRCMcg8QuzsXUWG8B1YgeqqtS+xlWp/YzHO+GuwKO6y1AgdhPVFrFlcgBKdwke6NFToMAAAAASUVORK5CYII=",
    "icon_redo_again":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA9klEQVQ4jc2S4W3CQAyFbwNG6AgZAQkVVdBc7uCSXHI0ATdQUlLRETJSRsgIHSEjeARXR4maRqUF/rRP+v742ZZlPcb+vYqX/duu2DtXL8ifC7Js893rVQs2Tzl1qNeb7c1ZgwDZECAr4XFNPRAg+/6aJF0NknRVpkvAdAn0C5XtZ62MeXDMIkGzSOgC8DAc6tjROkatY7qAJorMkCkVDJQfNsoPqQP6ga4tvfoBP9BVEEYf50s5L6Wc05F6NlOi+5eOZ8G+z1zXa1wukHPx1Wh9LsjCuag8T34+rdVkco/TqXsyaUf/dIhGo9sfEzYe350XnD/TOzp3s5E0siCKAAAAAElFTkSuQmCC",
    "icon_restrict":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA4ElEQVQ4jaXRTY6CQBAF4LrBHKUPQIgLQgZtW2NURsYxDtjS0wh69HeEMuUKDY4/VPKt6r1NFVFrDvVR1c0JdXPiOyAZ6hpf1cpXDXzV8AOQ7FW5dF6VzsP9VfwMyUrnUt7ZUtm9g907fhGkS3lhkReW3wTa/hbcB/1sttwHZdma277Xm8F/bvOUfmXctkxXH51/JiLZ3eZpvki5D5rN5twHGTOFMVN+E2g8niitDbQ2/CJI93Kc4VCrJBkhSUb8JEjn6sJx/KmiKEYUxfwAJNv5pjAcqCAIEQQh3wHJtDtnc8+0gjJf23AAAAAASUVORK5CYII=",
    "icon_rev":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAANCAYAAACdKY9CAAAACXBIWXMAAAsSAAALEgHS3X78AAAA1UlEQVQokX3RMUoDURDG8d8V7ITYBbWxEESSSuy9gI2VlTewsbexUPAGVmkEa88gWAghsVIUBSsFEwwxMjILm7C7Hwzv4838efNmmNc67tL3saxBa2jjB1t4xG0T8IpDDPGAUzw1ARe4wQHGOMd3KX+EpTCtbKWDCfYxw1meGwkEvBPmGs95GS28Z3KSwCW203eLF15wj91MlOMDV+lXiv428YU3/FZAs3xxTnv52ariiM+qSfUagEEVsIpRDXBct49ITBeK438x+lqdZM+x/VhmDOVffx7JTKTvAiHGAAAAAElFTkSuQmCC",
    "icon_rocket":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABKUlEQVQ4jZXQ8Y2CMBQGcDZgBEfgf2JijJcgR0AQqSDGQi1XITSM4AiM4AiM4ggdgRHepYkmylnlvuSXPJJ+L6WaNjI1b/SaN7jmTVfzRtS8AUkbk7KqJ2XFRVlxGNI+5YeVmJ0qYKeqZaeqv8134m2ZFsygBYMHLS1Y//DdKct5ftRzQkVOKAy0OaG9nAmhWLkAZ6TDGQGFFmdEZPlRf1lO9wec7g/wweRlOY53RpKkfZKkoLTbP189QrERoXgmIRRfEYpBQWy3ifFUDsPoEm4QjNBtou3ff/b9tfD9NbzRB0Gofm2Z1SowPM9vXXcFA1fP85+vrIrjuGfHcWFgNqosY9uOvlx+ny3Lbi3LhpvxC+5ZLL6M+XwBkpz/vUDGNKfCNKeXMWd/AcFP70MISzB3AAAAAElFTkSuQmCC",
    "icon_satellite":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABK0lEQVQ4jYWT222DMBRAvQEjZIQOEFVRaD8QwRhCA6WQQBDvgDxCRugIHiEjdISOwAiMcCtHUFFi0yMd2b5+vxAaaFraNy29oQWalpKhHXuorC8tq2puo4g6V3VDq7qFUeEMZXVRirLu8qLaTON5UbGirGHmk3CQLC83WV5CmhVXXk6zgvHy3KWtoiRJr+ckhXOSdkM6t0P/EcVJF8UJSLyvTkoQnlh4jEBifzzFwoO+4/sB8/0ApH6EFMlw3Xfqej7I9Dz/8f5HHOdAnDcXFnUOBMmwrH1v2w4I5PEvnres/bewMyG2YpoWw5jAxM40rU9ehzG5jXEDkxVawsDkzwvTdWO122GYKD9EEZqmU03TYaJ4GzJU9aVT1VeYut2q8ncwZ71+BoG/n+0HSGTucSuLZFMAAAAASUVORK5CYII=",
    "icon_security":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABMklEQVQ4jZ2TDY6CMBCFewOP0HsQssafrC7ColshsKAoQUgR9Qg9wh6hR/AoHoUjzGYIECGIxpd8yevMvCbQlpAOHbPz4JidRXa65Ah6rJFn4mlGeZoJnmY5T0/QBGtFjzZCccJpnPBLnPBrnHB4kWuZoSQ6JCI6JPAmguzDSOzDCN5EkGAXimAXQgtZ8mhdIYjnb4eev4UWEv+Pvwkkgh5rHXND8uttBq7rQRvH9YogCn3XDGYJyradm2070KLeAH1H/1YfJWPWH2MW1KztIsyYJZHCr23ZmhH1BqsVo8vlD9whSx6tATONC2UYpjQME16k/jxSabEwqKbpuabp8IRc17+738V8rpmz2Rf0gTO9D2o6/TTH40k+Gk3gHqxhrzdcSVU/qKKoUlFUKJFY65r9B39iaV2oZWG6AAAAAElFTkSuQmCC",
    "icon_shovel":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABNklEQVQ4jZWR/Y2CMBiHuwEjOEIXIOQSY86gqFgoFlAs8lE+PEdglBvBERyBERzhHaEXPM8Yc1b8JU/6vn88vyYtQj1T1V+43h+gqg/f6N0UZT0oyj0U5b79Pev3SnJRNrkoz6KoNFFUOBclZHnRvyTNRJNm4nS34zQTkKR5vxIeJw2Pk1sB5zuNx0nL4wReypuI42gbw5XTlXO3b/kOK+Ug3OBwHUG4jmR3rjfb5o6BUmYswIwFwPxQMj8E3w/Vt7l0pbl0Nb/OmNIVUI9J6jHwPKaWCXEHxKEtcagkxG2IQ+EyOxQc11PLi8VSs20Ctk3kA7BcOmq5i2XNj7PZQj5iWfMG9clkYslnmOb08ibKjMemfEJrmlPtZcFwOJL/AKPRp/qf/6LrRqvrhrzjaBgf/WSE0A/N5LL+NljPCgAAAABJRU5ErkJggg==",
    "icon_shuffle":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABXUlEQVQ4jZ2T/3GCMBSAs4EjMAITKNXWK4hADiQVARMiQsEfHYERGIEROkJHyAiOwAjptcYepviHvrvvknvfe+9yyQWAO2O3P6q7/XEAHo2iPFRFeWBFuT8PyfJC6yI3ZHmhSDVN/l7yLC9YlhcDkG5zLtGm29z5aU63ed3juzCQ0JTLUJpWCU3rPifBAEk22gVMaIUJ5ZhQFRPain1Lkg3u1DQiz0iy+X+ZUYxxGK0/ohhzAZZ8FcWYxWty+yWCIDwFQciDIGxXYXxVuApjRc5dBUJLB70FXFBfWwB8tFR8tLw9wFugL2+BuED1PN+RfOUtEPM8/zwEQlfrUEHocsEnhC6G0G3FeqlphGcQugNgWQ7vw7ahZlnO6ZYXMGCaFpdo53P799jm3K57fBcGDMPUush3Yhim0vW6Pmt0fcZ1fcYMw7z/U43Hz9Vk8sKm09fHfuRwqKmj0dNf8zcJLgamkGkfrgAAAABJRU5ErkJggg==",
    "icon_sofa_chair":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA9UlEQVQ4jaXTUYrCMBQF0LcDlzD7KNLEDylTOlhaqSgOqVaqtTXiCrIUl9IlZAkuwSU8ycAMr2lLRw2cjwv35isBsM5JXsRJXlQPAX3nWMpRWUldVhIHaNNtXXAoqmtxrPA/TLd1Qb4v8BmNcbbLP7Jdjs/4G4t0exbpVhnpJtPpJsMB+rdvtrD+FkicrdxF0Qyr1RoJZuUujQ4kiyUSzMpdGh2I5wkSIp4n9QBBNxCGERK3MIzqATe6geBrhu8A3w/uvh/gi+7geZ9iOvXwFWb785g4nzDGJsp1Obou14zxuo/pmK7ZtP6D44yV44zbP83q0PwA4nmcr9TUCBoAAAAASUVORK5CYII=",
    "icon_sport":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABJ0lEQVQ4jY2TcWqDMBSHcxPvYTtECq0LSkVxSO3MQiTWKV7BI+QoHiFHyJHeyBa2NDrbBx+8fL/3xD8ShJz67EfSD6PshxEcpM7QVt26Qd26AR6gFou87TzedoK3HeFtBw8gZtb7/QBruGINB9ZwwRo+m36N2czo/udPPigjlDKwCJzzv5neRTWhsiYULERN6Ow4ME44TqLqWoPNpXpX1bWeXK+dye48KssLrBA86QAVbyWsEDzpAOV5AQ4qz4tpxU8mu/MoTTOZphlYiDTNZseBccJxEiXJmSTJGSwC57yVke+7gHGsMI4B41hgHM+mX0Nnekb3f1c6irAXRVgcjxE5nV5hCz2jZ/XO4k2E4UGF4QEesHxMdu12L8T399L39+AgdebOfwG3sJ0M9HY2GgAAAABJRU5ErkJggg==",
    "icon_star":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABD0lEQVQ4jZ2S4W2DMBCFvQH7ENrK0CYUEYFCHVxC7SAiEpSoKzBCRskIjOAROoJHuOraqKKJUwonfdLp7t378WxC/qj94b1ByNja1QeNjDqutrWstjWckYMNyk2lyk0FZ9Sg43VRPhRFCV1wZhS/iXVziZBFK2QBF7QmLVnlol3lAkbSkizLLc4zxXkGA1F4S7DS9NViS67YksM/UXjzK4sXllpJwlSSMOjhA7XGQON4EcXxAnqIbj5fOI+O4TyCHo43DYIg1EEQQg/mrz2d+nI2e4YO2veDBsG+u0PtlQGl7olSDyj1tOs+Np739BMU9jjD3bfGPV0Z2LajJ5O7xnHuzQkTQnCHGtTatvOl+wTbrQ5fzxbYNgAAAABJRU5ErkJggg==",
    "icon_stop":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABvUlEQVQ4jXVSjXGyMBjOBo7ACA7QCth+PaxIiWIRlBpMoQhCHYFRGMURGIUR8t2TppZylbvn7n3+eC8QQgZPWZ1ZWZ0vZXUWA0Bj5NaTF6WWF1WbF5UoTlVTnD7dU/lpAJihwfvKlNqv8keWa9mx6LJj0R7z0/jWEnjIIIvO1UjSrAU+snyUpBlQJ2nWJWkmFDDXatnoOy/LB56wA08Ef0/l5gNPWvAh+Ht6PT+ySmeExfzCYt7AYDGvWczFEHHMZXnPDgwZlW3QJdEbE9EbcyHuon2neB+yvIv2DBwZcHTASRjuRBjujCDYjtT8g20ky0GwZX0dGjpy9jeh8P1gjBfIWWGzCWX51Q9YXweg+5vQkLO39oW39uURvLXfKS7LnvfKFO9DHgEdcELp6kLpSn7E5dKrl0tPlildMUpXYghklN+gS5wXyhzHFQvHvV6gheNK7Q/If4+s5C/069fattMC8/lipHht205n245QwCw3I/Odv97E2WyuzWbzzrKeW8t6vnmV4SGDLDq/zKcnS3t4+NdOp4/CNKeNrpuurpuGrptjzNDgIYPsrSVkMjHY/b1+ububiD6gwRvm/wMtlkB5IiA0UgAAAABJRU5ErkJggg==",
    "icon_thumb_down":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABBUlEQVQ4jZ3S4WnDMBAFYG2QETJCFnCsggmYGKc1jiSLJCgxThUpVjxKR/AIHUEjdASP0BGu1JHBlJZGfvCBBKf3R4fQKNf6hq/1ra1N09WmgX8s+kdKG6u0AaVNp7T5dOdH4L5AXrSVFw2+XqWyfUF1lrY6S5gIo1NZ2VNZwUQYiWNpxbGEiVq0Pwi7PwjwYEcaxPnOcr6DiQSijFvKOFDG3xjjgjLeufsjBCK0WBBaYEKL+fevEFrMtoS1+ZbCT25ucF+kv5JleZtlOYwh32w2L+9p+gwD74IkSXGSpDDwLojjNY7jNTj31fVJFK1wFK3AabwLlks8D4IQgiD8CMOn2W8zX5TzWwjoQtaHAAAAAElFTkSuQmCC",
    "icon_thumb_up":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABAklEQVQ4jZ3S0WnDMBAGYG3gETqCF1CsB2EQNkpqlDoIuVZtHJw4djxCR+gIHiEjaISOkBE8whVSBdI+BEsHHzoE//90CD2ZU39+6YcR+mH8PvXnALnOsRvIsRvAGp0L2kNH2kMHlnEuaPYtafYt3DkXVHVzqeoG7pzCpa4m/VHDo0VBVZSBKspL8a7hP1WU5EH4JyilCqRUWkp1lVLBQhrlO2nynQRPGoltbsQ2Bw+zEG8jyjJhskyApwlxvjGcb8DHev0aojTlJk05eCKIscQwlgBjyWzfpX5Pm9LYUBoDpfEXpfFs9yXIrQDjyGAcAcbR52pFQoyjCePoav+euR3SD0mvQOJx4DncAAAAAElFTkSuQmCC",
    "icon_tool_box":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAqUlEQVQ4jWNgGJQgJzffPyc3vx4N+xOlOSMzWz4zK+d/ZlbuflSc8x+nppTUdP3UtIx6JPwfjY8hBtID1pyYmKyfmJTyPjEp5T+J+D1IL0NsXML72LiE/zjwfSjGJf+eITIqZj8erB8VFWOPTw1DaFjEfzzYHopxqmEIDAz+jwefDwwMvo9PDYOvr/9/SjCDp6f3f0owg6Oj839KMIOVlU09JZhq+YdsAAB0vTbwE/9cDgAAAABJRU5ErkJggg==",
    "icon_trash":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAAsElEQVQ4jZ3QYQqCMBjG8d3A+wwhog8SIkqFJIahzJbL5RE6yo6yI3WEJwbVl9cPvr7wgzG2P2xCzMxop2i0kx/thK+wjsTSGYz1g7Fv83jmQViHvdnDNz1s9N1gjXBXqF471Wus5ETbKd92Civ5/1Oaa/viIH9RXxpwkEBV1eAggbI8g4MEjqcSHCRQFAdwkECW5eAggTTNwEECSbIHBwlstztwkICUsZMyxkLud+8DfgN1JBFkZbYAAAAASUVORK5CYII=",
    "icon_trophy":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABAElEQVQ4jZXQ0W2DMBAG4NuEETJBxEtUKUrBjVKFYEFsHBODA2WEjMQIGYURGOGqax2prSowJ33SCd9/MgYAgFvz0d2arm/aDn3QLGUoC7Vt+9q2Y23bobYtehpcpgdTWTSVZaayd9f7oFlBPejSoC5N6KCP8lqx5zwUSg+F0g+l9KpQGn2oSxlQhrIgi8tKSDUKqQYhFXqi2VFKFX49ZH6WQX6Wd5LlAqc85ygD/xXnmUh5NqY8wz9GOgOfOp14kCTp45ikSKinb7C0Du9HdL7/dWnt9wd0li2IIhbG8Rv+FEWMeYV3rzHOmL7NdrvDGdMLNpsXnDG9YL0OccavBZ85ekeqQ9SMbAAAAABJRU5ErkJggg==",
    "icon_umbella":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABBElEQVQ4jaWS4W3CMBCFvQEjZAQGgBbh9kcEihAi5GTLlanBJHEJsEFHyQgZgRE6AiN4hKuuSitBBcXlpE+6O733ftjH2JWqtvtoU+2RhVTpqk7pKl266p1wb1tse9p1LhrzwkV54eq8cPgHpIlOzCubd+268HZd4I148nyZX82qa5bWm6XFQDx5mV6YRi8M/pOGqReN98CkVLWQ6iCkwhDIJ6Vqfh4SQDQZCMxAHAHEIQPh25nw7e5IM4DY/frGdA5ROofJ2U7P0uzkkEhD2psPazqdhV3ieSXJ5L6A8TgJD4jjEcbxaPDdBwdw/oycP+nhkA+oDw7o9x/rXu8BWz6uaT8B3S/+g20GLk0AAAAASUVORK5CYII=",
    "icon_undo":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA90lEQVQ4jc2RUW6CQBCGvQFH8AgcwcRoGu0uu7rAwlrQEVAqjRyBI3EEjtAjcIQ9wjSYaMUqLX1oOsn39O3/JzszGPzbOWRHM3s7vv8qvE8PefqaYUOvYJzsh8kurZJdimd+HAaIctjGGrYxtoCoAIhGD4NBuDHCNZThGvAbdBBuiuZ9q0CtAq1WAfZAK/ViXgo8T42k9GspfeyBdqX/WeK4nmE7shS2i7fYjqwahO3qG1cL4bS/s1gIxvlSc77EM3d8deWLL0u1LG5QykpCGTbcWzyljBHKNCFW/fA68znJZ7Nn3eHNLn+a6fRp2OXH40neWfAn8wFRBbOR2xZaJwAAAABJRU5ErkJggg==",
    "icon_unlock":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAAA/0lEQVQ4jZWQUYqDMBRF3UGX4BJcgTwGLEhb0orFEiKxSjRJE+xSXEKXMEtwKbMEl/AGQcjUDzu5cH4u756PFwSrGNuHxvajsT3+YTC23wWforTZKW0n/bC4Rmk7fhR0Ur86qbGT+kdpE86dVI/z0s2cNwWilaNoJYpWvh2KVg5LP2wK6kaMdSOwbgSs+mrptwXVvRmre4O8qp+Bb1jJI1byFys5spJ/s5LDBtHbmFIWUcrQEycpbhSKG0VP3J/yawH5tUBPnCDLcsiyHD1xAkIuQMgFPXGC44nA8UTQEydI0wOk6QE9cYIk2UOS7NETJwD4CuMYpjgG/CfTvJm3vzVnPJNXCHAmAAAAAElFTkSuQmCC",
    "icon_voice_command":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABQUlEQVQ4jY2SjXGCMBTHs4EjOIIDoEVp75AURAxN/QCDWCxCDW7gCIziCBnBERyBEV4PS09UFP93v8vdu/eR/F8QqtGGb5sbvk02fLsrIdfVoSjmjSjm+/iHQxVRzNOHDcJ1nITrGB7xHUb3bxKsQhGsQqhhf0pe+F+NnHIDfxkIfxlADdkp2fN84Xn+X7dCRQzqQLnmbNFwXCZmzpz9N3BcdnRcBnWgsqYz18zPydRhk6kDz4A+6Lh1bSCl4yP9nMAzIGJTIDbNiE1TYtOTkcSmxyJeh0CWRdhoZDerVmlZRB4OR/CA9KJAN8yb5xiGKQzDhCoGg+F5sKa9pxjru3IxxvoBYx3ucF67qmpCVbXD9fQ8pqoaVJD1+/g8XVHeWoryeuNDt9tLZLkHV2R5fpVnlZKkDpOkzq4gabdfLr78LzMlMXlwSHAoAAAAAElFTkSuQmCC",
    "icon_walk":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABPUlEQVQ4jZWQ/42CMBTH3cARHMEBQPmjkmvgKtf0xIOrV+GKBQ7CCIzgCI7gCIzgCI7ACL1gqpHcj+JLPul7r3nfvn5Ho3+iKKtJUVZtUVayKCtr9GhkeWlleSkV1UPDO5ExkeYnkeZSpPkxzb7G2iGeiAlPRM0T0Sa7VF7hiTgOejWKeR3FvI1ifo5iLntEnxOtANvGNdvGjTplDxYdtAJ0w2pFQzdMKk53dfNOP/72Igwp6whCKu9g6s4KQtoEIdX74a+D1l8H8oL/pl/9PghZjcmrL3uQld7Aa2BMGMZEYkzOGJNW5cO3QMg7IORJhLxquXyZqrwZLOC6qO14Rt7FbddFp64eNAyhY0HoSAid28oQOvuuN0gAgMUeAFva9tPNNABsq+sBsJhqBQxjdjSM2Y//mua8Mc35rwLfg2GojkkRJboAAAAASUVORK5CYII=",
    "icon_weather":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABXUlEQVQ4jaWS/42CMBTH2cARHMEFiKD3B9FIij8OrwUsUFqK9SA3ASM4giM4giMwAiMwQi+988gZldzpSz5p3/u+9/LyWk3rsPf8o689Y2KXl2KXD378rchBZwHPRE/xy9/zTJx4JgqeCcAzUXU2SPm2x9KsoowXlPETSzPJ0qw+IynjNWW8neimkYSBmFAZE1olNG13oO4qFhPaxIQWMaF7krB22tbCMD6EEamjOLkSVUxpYUSaKCKXk/gBxn6ASz/AMtiE+N6ESlM5V4Lnb/rICwqE/COE3hEhXyog8k8Qeu32EfKNrzj0rp/41X3D7hrKWyhN5bhraJxjlbuG5UWD5cptlitX3qE55xyWK/fyOQGYYwDmpeMsZBcqB4D53nEW6vxesm2Dg20D+QDNzAZYm05n8hk0y5o0ljWRj6KNxy/ANEe1YYzkfzDNcaVq20Xq+nCg60Pjj7S/9BMKcBvwiPYelQAAAABJRU5ErkJggg==",
    "icon_wtg":
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAABCAYAAAD5PA/NAAAACXBIWXMAAAsSAAALEgHS3X78AAAADklEQVQImWMoKqr9j4wBTW0JgUnBaSwAAAAASUVORK5CYII=",
}
"""Every stock status icon as a PNG data URL, keyed by `image_map_key`."""

#: The keys the status picker offers, in the site's order.
STOCK_ICON_KEYS: tuple[str, ...] = tuple(STOCK_ICON_DATA_URLS)

_native_by_code = {s.code: s for s in NATIVE_STATUSES}


def is_native_status(code: str) -> bool:
    return code in _native_by_code


def native_status(code: str) -> NativeStatus | None:
    return _native_by_code.get(code)


@dataclass
class DataIconSource:
    """A bundled image, drawn from the data URL."""

    src: str
    cell: SpriteCell
    kind: Literal["data"] = "data"


@dataclass
class SpriteIconSource:
    """A cell of the sprite the site serves."""

    src: str
    cell: SpriteCell
    kind: Literal["sprite"] = "sprite"


@dataclass
class NoIconSource:
    """Nothing to draw."""

    kind: Literal["none"] = "none"


StockIconSource = Union[DataIconSource, SpriteIconSource, NoIconSource]
"""How to draw a stock icon: a bundled image, the site's sprite for a key outside the status set, or nothing."""


def stock_icon_source(image_map_key: str | None, site_url: str | None = None) -> StockIconSource:
    """Resolve an `image_map_key`.

    Status icons come from the bundle. A key outside the status set is still a sprite
    cell, so it draws only when `site_url` is given.
    """
    if not image_map_key:
        return NoIconSource()
    cell = STOCK_ICON_CELLS.get(image_map_key)
    if not cell:
        return NoIconSource()
    data = STOCK_ICON_DATA_URLS.get(image_map_key)
    if data:
        return DataIconSource(src=data, cell=cell)
    if site_url:
        return SpriteIconSource(src=site_url.rstrip("/") + STOCK_SPRITE_PATH, cell=cell)
    return NoIconSource()


def sprite_style(source: SpriteIconSource) -> dict[str, str]:
    """Inline style for a sprite-backed icon element sized to its cell."""
    return {
        "width": f"{source.cell.w}px",
        "height": f"{source.cell.h}px",
        "backgroundImage": f"url({source.src})",
        "backgroundPosition": f"-{source.cell.x}px -{source.cell.y}px",
        "backgroundRepeat": "no-repeat",
    }
