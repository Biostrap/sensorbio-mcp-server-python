from sensorbio_mcp_server.utils import expand_date_range, cursor_from_next_link


def test_expand_date_range_single():
    dr = expand_date_range(date_str="2026-02-20")
    assert dr.dates == ["2026-02-20"]


def test_expand_date_range_start_end():
    dr = expand_date_range(start_date="2026-02-18", end_date="2026-02-20")
    assert dr.dates == ["2026-02-18", "2026-02-19", "2026-02-20"]


def test_cursor_from_next_link():
    assert cursor_from_next_link("https://api.getsensr.io/v1/x?cursor=abc123") == "abc123"
    assert cursor_from_next_link("https://api.getsensr.io/v1/x?page%5Bcursor%5D=zzz") == "zzz"
    assert cursor_from_next_link(None) is None
