from render_checks import compute_render_diff, extract_visible_text


def test_extract_visible_text_strips_scripts_and_styles():
    html = (
        "<html><head><style>body{color:red}</style></head>"
        "<body><script>var x=1;</script><p>Hello world</p></body></html>"
    )
    assert extract_visible_text(html) == "Hello world"


def test_extract_visible_text_collapses_whitespace():
    html = "<p>Hello\n\n   world</p>"
    assert extract_visible_text(html) == "Hello world"


def test_compute_render_diff_identical_content():
    html = "<html><body><p>Same content here</p></body></html>"
    result = compute_render_diff(html, html)

    assert result["checked"] is True
    assert result["word_count_delta"] == 0
    assert result["text_similarity_ratio"] == 1.0


def test_compute_render_diff_detects_added_content():
    raw = "<html><body><p>Just a title</p></body></html>"
    rendered = (
        "<html><body><p>Just a title</p>"
        "<p>Extra JS-loaded content appears here now</p></body></html>"
    )
    result = compute_render_diff(raw, rendered)

    assert result["word_count_delta"] > 0
    assert result["text_similarity_ratio"] < 1.0