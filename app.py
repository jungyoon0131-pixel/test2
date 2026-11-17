"""쇼핑리스트 Streamlit 앱 (PRD.md 참고).

구현 원칙 (PRD 6.4)
- 모든 상태 변경은 위젯의 on_click / on_change 콜백에서 처리한다.
- 위젯 key는 아이템 id 기반으로 만든다. (chk_{id}, edit_{id}, del_{id} ...)
- 수정 중인 아이템은 st.session_state.editing_id 하나로 관리한다.
- 변경할 때마다 파일에서 최신 목록을 다시 읽어 수정하고 바로 저장한다.
  (탭이나 접속자가 여러 명이어도 서로의 변경을 덮어쓰지 않도록)
"""

import re
import uuid
from datetime import datetime

import streamlit as st

from storage import load_items, save_items

st.set_page_config(page_title="쇼핑리스트", page_icon="🛒", layout="centered")

MAX_NAME_LEN = 50
MIN_QTY, MAX_QTY = 1, 99


# ---------------------------------------------------------------------------
# 데이터 처리
# ---------------------------------------------------------------------------
def normalize(item: dict) -> dict | None:
    """저장된 아이템의 누락/잘못된 필드를 보정한다. 이름이 없으면 None."""
    name = str(item.get("name", "")).strip()
    if not name:
        return None
    try:
        qty = int(item.get("quantity", 1))
    except (TypeError, ValueError):
        qty = 1
    return {
        "id": str(item.get("id") or uuid.uuid4()),
        "name": name[:MAX_NAME_LEN],
        "checked": bool(item.get("checked", False)),
        "quantity": min(max(qty, MIN_QTY), MAX_QTY),
        "created_at": str(item.get("created_at", "")),
    }


def fetch_items() -> list[dict]:
    """파일에서 최신 목록을 읽어 보정한 뒤 반환한다."""
    return [n for n in (normalize(i) for i in load_items()) if n]


def commit(items: list[dict]) -> None:
    """목록을 저장하고 세션 상태에도 반영한다."""
    save_items(items)
    st.session_state.shopping_items = items


def find(items: list[dict], item_id: str) -> dict | None:
    return next((i for i in items if i["id"] == item_id), None)


def is_duplicate(items: list[dict], name: str, exclude_id: str | None = None) -> bool:
    """대소문자/앞뒤 공백을 무시하고 같은 이름이 있는지 확인한다."""
    key = name.strip().casefold()
    return any(i["name"].casefold() == key and i["id"] != exclude_id for i in items)


def validate_name(items: list[dict], name: str, exclude_id: str | None = None) -> str | None:
    """이름이 올바르면 None, 아니면 경고 문구를 반환한다."""
    if not name:
        return "아이템 이름을 입력해 주세요."
    if len(name) > MAX_NAME_LEN:
        return f"아이템 이름은 {MAX_NAME_LEN}자 이하로 입력해 주세요."
    if is_duplicate(items, name, exclude_id):
        return f"'{name}'은(는) 이미 리스트에 있어요."
    return None


def sorted_items(items: list[dict]) -> list[dict]:
    """미완료가 위, 완료가 아래. 각 그룹 안에서는 추가된 순서."""
    return sorted(items, key=lambda i: (i["checked"], i["created_at"]))


def md_escape(text: str) -> str:
    """사용자 입력이 마크다운으로 해석되지 않도록 특수문자를 이스케이프한다."""
    return re.sub(r"([\\`*_{}\[\]()<>#+\-.!|~:$])", r"\\\1", text)


def flash(message: str, kind: str = "warning") -> None:
    """다음 화면 렌더링 때 보여줄 메시지를 남긴다. (콜백 안에서 사용)"""
    st.session_state.flash = (kind, message)


def forget_widget_keys(item_id: str) -> None:
    """삭제된 아이템의 위젯 상태를 정리한다."""
    for prefix in ("chk_", "edit_", "del_", "edit_name_", "edit_qty_", "save_", "cancel_"):
        st.session_state.pop(f"{prefix}{item_id}", None)


# ---------------------------------------------------------------------------
# 콜백
# ---------------------------------------------------------------------------
def on_add() -> None:
    """F-01 아이템 추가 (+ F-09 수량, F-11 중복 경고)"""
    name = st.session_state.get("new_name", "").strip()
    qty = int(st.session_state.get("new_qty", 1))
    items = fetch_items()

    error = validate_name(items, name)
    if error:
        flash(error)
        return

    items.append(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "checked": False,
            "quantity": qty,
            "created_at": datetime.now().isoformat(timespec="microseconds"),
        }
    )
    commit(items)
    st.toast(f"'{name}' 추가했어요.", icon="✅")


def on_toggle(item_id: str) -> None:
    """F-03 체크/해제"""
    items = fetch_items()
    item = find(items, item_id)
    if item is None:
        flash("이미 삭제된 아이템이에요.")
        return
    item["checked"] = bool(st.session_state.get(f"chk_{item_id}", False))
    commit(items)


def on_edit_start(item_id: str) -> None:
    """F-04 수정 모드 진입 (한 번에 한 개만)"""
    item = find(st.session_state.shopping_items, item_id)
    if item is None:
        return
    st.session_state.editing_id = item_id
    st.session_state[f"edit_name_{item_id}"] = item["name"]
    st.session_state[f"edit_qty_{item_id}"] = item["quantity"]


def on_edit_save(item_id: str) -> None:
    """F-04 수정 저장"""
    name = st.session_state.get(f"edit_name_{item_id}", "").strip()
    qty = int(st.session_state.get(f"edit_qty_{item_id}", 1))
    items = fetch_items()
    item = find(items, item_id)
    if item is None:
        st.session_state.editing_id = None
        flash("이미 삭제된 아이템이에요.")
        return

    error = validate_name(items, name, exclude_id=item_id)
    if error:
        flash(error)
        return

    item["name"] = name
    item["quantity"] = qty
    commit(items)
    st.session_state.editing_id = None
    st.toast("수정했어요.", icon="✏️")


def on_edit_cancel() -> None:
    """F-04 수정 취소"""
    st.session_state.editing_id = None


def on_delete(item_id: str) -> None:
    """F-05 아이템 삭제"""
    items = fetch_items()
    item = find(items, item_id)
    if item is None:
        return
    commit([i for i in items if i["id"] != item_id])
    forget_widget_keys(item_id)
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    st.toast(f"'{item['name']}' 삭제했어요.", icon="🗑️")


def on_clear_checked() -> None:
    """F-07 완료 항목 일괄 삭제"""
    items = fetch_items()
    done = [i for i in items if i["checked"]]
    if not done:
        return
    commit([i for i in items if not i["checked"]])
    for i in done:
        forget_widget_keys(i["id"])
        if st.session_state.editing_id == i["id"]:
            st.session_state.editing_id = None
    st.toast(f"완료 항목 {len(done)}개를 지웠어요.", icon="🧹")


def on_clear_all() -> None:
    """F-10 전체 삭제 (확인 체크 후)"""
    if not st.session_state.get("confirm_clear_all"):
        return
    for i in fetch_items():
        forget_widget_keys(i["id"])
    commit([])
    st.session_state.editing_id = None
    st.session_state.confirm_clear_all = False
    st.toast("리스트를 모두 지웠어요.", icon="🗑️")


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
CSS = """
<style>
/* 본문 폭과 여백 */
.block-container { max-width: 640px; padding-top: 2.5rem; padding-bottom: 4rem; }

/* 헤더 카드 */
.st-key-header h1 { padding: 0; font-size: 1.9rem; }

/* 좁은 화면에서도 입력 줄 / 아이템 줄 / 하단 버튼이 세로로 쌓이지 않게 */
.st-key-add_row [data-testid="stHorizontalBlock"],
[class*="st-key-row-"] [data-testid="stHorizontalBlock"],
.st-key-footer [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.5rem;
}
.st-key-add_row [data-testid="stColumn"],
[class*="st-key-row-"] [data-testid="stColumn"],
.st-key-footer [data-testid="stColumn"] {
    min-width: 0 !important;
}
/* 첫 번째 칸(이름)만 늘어나고 나머지(수량, 버튼)는 내용 크기만큼 */
.st-key-add_row [data-testid="stColumn"]:first-child,
[class*="st-key-row-"] [data-testid="stColumn"]:first-child {
    flex: 1 1 auto !important;
    width: auto !important;
}
.st-key-add_row [data-testid="stColumn"]:not(:first-child),
[class*="st-key-row-"] [data-testid="stColumn"]:not(:first-child) {
    flex: 0 0 auto !important;
    width: auto !important;
}
.st-key-add_row [data-testid="stNumberInput"],
[class*="st-key-row-"] [data-testid="stNumberInput"] { width: 6.5rem; }
@media (max-width: 640px) {
    .st-key-add_row [data-testid="stNumberInput"],
    [class*="st-key-row-"] [data-testid="stNumberInput"] { width: 4rem; }
}

/* 아이템 줄: 얇은 구분선 + 손가락으로 누르기 좋은 크기 */
[class*="st-key-row-"] {
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
    padding: 0.3rem 0;
}
[class*="st-key-row-"] button { min-height: 2.5rem; min-width: 2.5rem; }
[class*="st-key-row-"] [data-testid="stCheckbox"] p {
    font-size: 1.05rem;
    overflow-wrap: anywhere;
}
/* 담은(완료) 아이템은 흐리게 */
[class*="st-key-row-done-"] [data-testid="stCheckbox"] p { opacity: 0.5; }

/* 빈 상태 */
.empty-state { text-align: center; padding: 2.5rem 1rem; opacity: 0.8; }
.empty-state .icon { font-size: 3rem; line-height: 1; margin-bottom: 0.75rem; }
.empty-state p { margin: 0.2rem 0; }
</style>
"""


def init_state() -> None:
    """매 실행마다 파일에서 최신 목록을 읽는다. (다른 탭의 변경 반영)"""
    # 주의: "items"는 session_state의 .items() 메서드와 이름이 겹치므로 쓰지 않는다.
    st.session_state.shopping_items = fetch_items()
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    # 수정 중이던 아이템이 다른 곳에서 삭제됐으면 수정 모드 해제
    if st.session_state.editing_id and not find(
        st.session_state.shopping_items, st.session_state.editing_id
    ):
        st.session_state.editing_id = None


def render_header() -> None:
    """제목 + F-08 진행 현황"""
    items = st.session_state.shopping_items
    with st.container(border=True, key="header"):
        st.title("🛒 쇼핑리스트")
        if not items:
            st.caption("오늘 살 물건을 적어 보세요.")
            return
        done = sum(i["checked"] for i in items)
        left = len(items) - done
        status = "다 담았어요! 🎉" if left == 0 else f"남은 물건 {left}개"
        st.caption(f"**{len(items)}개 중 {done}개 완료** · {status}")
        st.progress(done / len(items))


def render_input() -> None:
    """F-01 아이템 추가 입력 영역"""
    with st.container(key="add_row"):
        with st.form("add_form", clear_on_submit=True, border=False):
            col_name, col_qty, col_btn = st.columns([6, 2, 2], vertical_alignment="bottom")
            col_name.text_input(
                "아이템",
                key="new_name",
                max_chars=MAX_NAME_LEN,
                placeholder="살 물건을 입력하세요",
                label_visibility="collapsed",
            )
            col_qty.number_input(
                "수량",
                key="new_qty",
                min_value=MIN_QTY,
                max_value=MAX_QTY,
                value=1,
                step=1,
                label_visibility="collapsed",
            )
            col_btn.form_submit_button("추가", on_click=on_add, type="primary")

    if "flash" in st.session_state:
        kind, message = st.session_state.pop("flash")
        getattr(st, kind)(message, icon="⚠️" if kind == "warning" else None)


def item_label(item: dict) -> str:
    text = md_escape(item["name"])
    if item["quantity"] > 1:
        text += f" **× {item['quantity']}**"
    return f"~~{text}~~" if item["checked"] else text


def render_item(item: dict) -> None:
    item_id = item["id"]
    state = "done" if item["checked"] else "todo"

    with st.container(key=f"row-{state}-{item_id}"):
        if st.session_state.editing_id == item_id:
            # 수정 모드: [이름][수량][저장][취소]
            c_name, c_qty, c_save, c_cancel = st.columns(
                [5, 2, 1, 1], vertical_alignment="center"
            )
            c_name.text_input(
                "이름 수정", key=f"edit_name_{item_id}", max_chars=MAX_NAME_LEN,
                label_visibility="collapsed",
            )
            c_qty.number_input(
                "수량 수정", key=f"edit_qty_{item_id}", min_value=MIN_QTY,
                max_value=MAX_QTY, step=1, label_visibility="collapsed",
            )
            c_save.button(":material/check:", key=f"save_{item_id}", help="저장",
                          on_click=on_edit_save, args=(item_id,), type="primary")
            c_cancel.button(":material/close:", key=f"cancel_{item_id}", help="취소",
                            on_click=on_edit_cancel)
            return

        # 일반 모드: [체크 + 이름][수정][삭제]
        c_chk, c_edit, c_del = st.columns([8, 1, 1], vertical_alignment="center")
        # 체크박스 상태를 파일 데이터와 맞춘다. (다른 탭에서 바뀐 경우 대비)
        st.session_state[f"chk_{item_id}"] = item["checked"]
        c_chk.checkbox(item_label(item), key=f"chk_{item_id}",
                       on_change=on_toggle, args=(item_id,))
        c_edit.button("✏️", key=f"edit_{item_id}", help="수정", type="tertiary",
                      on_click=on_edit_start, args=(item_id,))
        c_del.button("🗑️", key=f"del_{item_id}", help="삭제", type="tertiary",
                     on_click=on_delete, args=(item_id,))


def render_list() -> None:
    """F-02 목록 표시 (살 물건 / 담은 물건 섹션)"""
    items = st.session_state.shopping_items
    if not items:
        st.markdown(
            '<div class="empty-state"><div class="icon">🧺</div>'
            "<p><b>리스트가 비어 있어요.</b></p>"
            "<p>살 물건을 추가해 보세요.</p></div>",
            unsafe_allow_html=True,
        )
        return

    ordered = sorted_items(items)
    todo = [i for i in ordered if not i["checked"]]
    done = [i for i in ordered if i["checked"]]

    st.subheader(f"살 물건 {len(todo)}", divider="green")
    if todo:
        for item in todo:
            render_item(item)
    else:
        st.caption("모두 담았어요. 장보기 끝! 🎉")

    if done:
        # 라벨이 바뀌면 펼침 상태가 초기화되므로 라벨은 고정한다.
        with st.expander("담은 물건", icon=":material/shopping_cart_checkout:", expanded=True):
            for item in done:
                render_item(item)


def render_footer() -> None:
    """F-07 완료 항목 지우기, F-10 전체 삭제"""
    items = st.session_state.shopping_items
    if not items:
        return
    has_checked = any(i["checked"] for i in items)
    st.write("")
    with st.container(key="footer"):
        c_clear, c_all = st.columns(2, vertical_alignment="center")
        c_clear.button(
            "완료 항목 지우기",
            icon=":material/cleaning_services:",
            on_click=on_clear_checked,
            disabled=not has_checked,
            use_container_width=True,
        )
        with c_all.popover("전체 삭제", icon=":material/delete_sweep:",
                           type="tertiary", use_container_width=True):
            st.markdown(f"리스트의 **{len(items)}개** 아이템을 모두 지워요.")
            st.checkbox("정말 모두 지울게요", key="confirm_clear_all")
            st.button(
                "전체 삭제",
                key="clear_all_btn",
                on_click=on_clear_all,
                type="primary",
                disabled=not st.session_state.get("confirm_clear_all"),
                use_container_width=True,
            )


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    render_header()
    render_input()
    render_list()
    render_footer()


main()
