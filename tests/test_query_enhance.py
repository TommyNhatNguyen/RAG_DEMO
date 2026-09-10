from app.generation.query_enhance import EnhancedQuery, build_enhance_prompt, parse_enhanced_query


def test_enhance_prompt_formats_without_json_keyerror():
    messages = build_enhance_prompt().format_messages(question="px vs dx")
    system = messages[0].content
    human = messages[1].content
    assert '"rewritten"' in system
    assert '{"rewritten"' in system
    assert "e-learning" in system.lower() or "e-learning" in system
    assert "px vs dx" in human
    assert "người học" in human


def test_parse_rewritten_and_subqueries():
    raw = """
    {"rewritten":"Định nghĩa quan hệ phản xạ","subqueries":["quan hệ phản xạ","quan hệ đối xứng"],"step_back":"Quan hệ hai ngôi là gì?"}
    """
    parsed = parse_enhanced_query(raw, "phản xạ vs đối xứng", max_subqueries=3)
    assert parsed.rewritten == "Định nghĩa quan hệ phản xạ"
    assert parsed.subqueries == ["quan hệ phản xạ", "quan hệ đối xứng"]
    assert parsed.step_back == "Quan hệ hai ngôi là gì?"
    queries = parsed.text_search_queries()
    assert queries[0] == "phản xạ vs đối xứng"
    assert "Định nghĩa quan hệ phản xạ" in queries
    assert "quan hệ phản xạ" in queries
    assert "Quan hệ hai ngôi là gì?" in queries


def test_parse_caps_subqueries():
    raw = '{"rewritten":"A","subqueries":["b","c","d","e"],"step_back":""}'
    parsed = parse_enhanced_query(raw, "A", max_subqueries=3)
    assert parsed.subqueries == ["b", "c", "d"]
    assert parsed.step_back is None


def test_parse_drops_step_back_if_same_as_rewritten():
    raw = '{"rewritten":"quan hệ phản xạ","subqueries":[],"step_back":"quan hệ phản xạ"}'
    parsed = parse_enhanced_query(raw, "quan hệ phản xạ")
    assert parsed.step_back is None
    assert parsed.text_search_queries() == ["quan hệ phản xạ"]


def test_parse_invalid_falls_back():
    parsed = parse_enhanced_query("not json at all", "câu gốc")
    assert parsed == EnhancedQuery.identity("câu gốc")
    assert parsed.rewritten == "câu gốc"
    assert parsed.subqueries == []


def test_parse_catalog_fills_subqueries():
    raw = '{"rewritten":"lộ trình môn quy trình nghiệp vụ","subqueries":[],"step_back":""}'
    parsed = parse_enhanced_query(
        raw, "Tạo lộ trình môn quy trình nghiệp vụ", max_subqueries=3
    )
    assert parsed.text_search_queries()[0] == "Tạo lộ trình môn quy trình nghiệp vụ"
    assert parsed.subqueries
    assert any("danh sách tài liệu" in item for item in parsed.subqueries)


def test_parse_strips_think_and_fence():
    raw = '<think>plan</think>\n```json\n{"rewritten":"quan hệ phản xạ","subqueries":[],"step_back":""}\n```'
    parsed = parse_enhanced_query(raw, "px")
    assert parsed.rewritten == "quan hệ phản xạ"


def test_hyde_not_in_text_search_queries():
    parsed = EnhancedQuery(
        original="px",
        rewritten="quan hệ phản xạ",
        hyde="Đoạn văn giả về quan hệ phản xạ trong giáo trình.",
    )
    assert parsed.hyde.startswith("Đoạn văn")
    assert all("Đoạn văn giả" not in item for item in parsed.text_search_queries())


def test_parse_hyde_and_reflect():
    from app.generation.query_enhance import parse_hyde_paragraph, parse_reflect_decision

    assert parse_hyde_paragraph("<think>x</think>  Quan hệ hai ngôi.  ") == "Quan hệ hai ngôi."
    decision = parse_reflect_decision(
        '{"needs_more":true,"follow_up":"quan hệ phản xạ chương 3"}'
    )
    assert decision["needs_more"] is True
    assert decision["follow_up"] == "quan hệ phản xạ chương 3"
    stopped = parse_reflect_decision("not json")
    assert stopped["needs_more"] is False
    assert stopped["follow_up"] == ""
