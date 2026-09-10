from app.main import build_parser


def test_ask_parser_flags():
    parser = build_parser()
    args = parser.parse_args(
        ["ask", "quan hệ phản xạ", "--text-only", "--no-stream", "-k", "8", "--show-hits", "--no-enhance"]
    )
    assert args.query == "quan hệ phản xạ"
    assert args.text_only is True
    assert args.no_stream is True
    assert args.k == 8
    assert args.show_hits is True
    assert args.no_enhance is True
    assert args.func.__name__ == "cmd_ask"
    default = parser.parse_args(["ask", "hello"])
    assert default.no_enhance is False
    sourced = parser.parse_args(["ask", "hello", "--source", "buoi_3.mp4"])
    assert sourced.source == "buoi_3.mp4"
    course = parser.parse_args(
        ["ask", "hello", "--course", "hethongquytrinhnghiepvu", "--content-type", "text"]
    )
    assert course.course == "hethongquytrinhnghiepvu"
    assert course.content_type == "text"
    search = parser.parse_args(["search", "hello", "--source", "assets/test/buoi_3.mp4"])
    assert search.source == "assets/test/buoi_3.mp4"
    rebuild = parser.parse_args(["rebuild-bm25"])
    assert rebuild.func.__name__ == "cmd_rebuild_bm25"


def test_ask_help():
    parser = build_parser()
    ask_help = parser._subparsers._group_actions[0].choices["ask"].format_help()
    assert "--text-only" in ask_help
    assert "--no-stream" in ask_help
    assert "--show-hits" in ask_help
    assert "--no-enhance" in ask_help
    assert "--source" in ask_help
    assert "--course" in ask_help
    assert "--content-type" in ask_help
    search_help = parser._subparsers._group_actions[0].choices["search"].format_help()
    assert "--source" in search_help
    assert "--course" in search_help
    rebuild_help = parser._subparsers._group_actions[0].choices["rebuild-bm25"].format_help()
    assert "rebuild-bm25" in rebuild_help
