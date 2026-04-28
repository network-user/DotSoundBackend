from __future__ import annotations

_PREVIEW_MAX = 120


def truncate_preview(text: str, max_len: int = _PREVIEW_MAX) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def _is_en(locale: str | None) -> bool:
    return (
        (locale or "ru")
        .strip()
        .lower()
        .startswith(
            "en",
        )
    )


def comment_like_copy(
    locale: str | None,
    actor_label: str,
    track_title: str,
) -> tuple[str, str]:
    al = actor_label.strip() or "Someone"
    tt = track_title.strip() or "Track"
    if _is_en(locale):
        return (
            "Comment liked",
            f"{al} liked your comment on «{tt}».",
        )
    return (
        "Лайк на комментарий",
        f"{al} лайкнул ваш комментарий к «{tt}».",
    )


def comment_reply_copy(
    locale: str | None,
    actor_label: str,
    preview: str,
    track_title: str,
) -> tuple[str, str]:
    al = actor_label.strip() or "Someone"
    tt = track_title.strip() or "Track"
    pv = truncate_preview(preview)
    if _is_en(locale):
        body = f"{al} replied on «{tt}»"
        if pv:
            body += f": {pv}"
        body += "."
        return ("New reply", body)
    body = f"{al} ответил на «{tt}»"
    if pv:
        body += f": {pv}"
    body += "."
    return ("Новый ответ", body)
