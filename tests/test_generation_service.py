from app.generation.service import GenerationService
from app.models.retrieval import RetrievalResult


class FakeRetriever:
    def __init__(self, hits: list[RetrievalResult] | None = None) -> None:
        self.hits = hits or []
        self.calls: list[tuple] = []

    def search(self, raw_query: str, k=None, include_visual=True, *, enhanced=None, source=None, course=None, content_type=None):
        self.calls.append((raw_query, k, include_visual, enhanced, source, course, content_type))
        from app.retrieval.retriever import process_user_query

        if not process_user_query(raw_query):
            raise ValueError("Empty query after processing.")
        return self.hits


class FakeChatModel:
    def __init__(
        self,
        text: str = "final answer",
        chunks: list[str] | None = None,
        enhance_text: str | None = None,
        hyde_text: str = "",
        reflect_text: str = '{"needs_more":false,"follow_up":""}',
    ) -> None:
        self.text = text
        self.enhance_text = enhance_text
        self.hyde_text = hyde_text
        self.reflect_text = reflect_text
        self.chunks = chunks if chunks is not None else [text]
        self.invoked: list = []
        self.streamed: list = []

    def invoke(self, payload):
        self.invoked.append(payload)
        if self.enhance_text is not None and isinstance(payload, dict) and payload.get("enhance"):
            return self.enhance_text
        if isinstance(payload, dict) and payload.get("hyde"):
            return self.hyde_text
        if isinstance(payload, dict) and payload.get("reflect"):
            return self.reflect_text
        return self.text

    def stream(self, payload):
        self.streamed.append(payload)
        yield from self.chunks


def _hits() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            id="1",
            score=0.9,
            content_type="text",
            content="Quan hệ phản xạ trên tập {1,2,3,4}",
            metadata={
                "relative_path": "assets/test/bai_tap_chuong_3.docx",
                "filename": "bai_tap_chuong_3.docx",
                "chunk_index": 0,
            },
        ),
        RetrievalResult(
            id="2",
            score=0.8,
            content_type="image",
            content="",
            metadata={
                "relative_path": "assets/test/Chuong_3_quan_he.pptx",
                "page_number": 2,
                "chunk_index": 1,
            },
        ),
    ]


def test_generate_answer_strips_think(settings):
    chat = FakeChatModel("<think>secret</think> Quan hệ phản xạ là...")
    service = GenerationService(settings, FakeRetriever(_hits()), chat_model=chat)
    answer = service.generate_answer("quan hệ phản xạ")
    assert answer == "Quan hệ phản xạ là..."
    assert "secret" not in answer
    assert chat.invoked
    payload = chat.invoked[0]
    assert "assets/test/bai_tap_chuong_3.docx" in payload["context"]
    assert "bai_tap_chuong_3.docx" in payload["source_paths"]
    assert payload["question"] == "quan hệ phản xạ"


def test_iter_answer_tokens_hides_think(settings):
    chat = FakeChatModel(
        chunks=["He", "llo <th", "ink>secret</th", "ink> world"],
    )
    service = GenerationService(settings, FakeRetriever(_hits()), chat_model=chat)
    visible = "".join(service.iter_answer_tokens("quan hệ"))
    assert visible == "Hello  world"
    assert "secret" not in visible


def test_iter_ask_events_order_without_enhance(settings):
    chat = FakeChatModel(chunks=["xin ", "chào"])
    service = GenerationService(settings, FakeRetriever(_hits()), chat_model=chat)
    events = list(service.iter_ask_events("quan hệ", enhance=False))
    names = [event.name for event in events]
    assert names[:3] == ["status", "sources", "status"]
    assert events[0].data == {"stage": "retrieving"}
    assert events[2].data == {"stage": "generating"}
    assert names[-1] == "done"
    assert "".join(event.data["text"] for event in events if event.name == "delta") == "xin chào"
    assert service.last_hits


def test_iter_ask_events_emits_query_when_enhancing(settings):
    settings.query_enhance = True
    enhance_json = '{"rewritten":"quan hệ phản xạ","subqueries":[],"step_back":""}'
    chat = FakeChatModel("ok", chunks=["ok"], enhance_text=enhance_json)
    service = GenerationService(settings, FakeRetriever(_hits()), chat_model=chat)
    events = list(service.iter_ask_events("px"))
    names = [event.name for event in events]
    assert names[0] == "status" and events[0].data["stage"] == "enhancing"
    assert names[1] == "query"
    assert events[1].data["rewritten"] == "quan hệ phản xạ"
    assert events[1].data["hyde"] == ""


def test_iter_ask_events_query_includes_hyde_paragraph(settings):
    settings.query_enhance = True
    settings.query_hyde = True
    enhance_json = '{"rewritten":"quan hệ phản xạ","subqueries":[],"step_back":""}'
    chat = FakeChatModel(
        "ok",
        chunks=["ok"],
        enhance_text=enhance_json,
        hyde_text="Đoạn văn về quan hệ phản xạ.",
    )
    service = GenerationService(settings, FakeRetriever(_hits()), chat_model=chat)
    events = list(service.iter_ask_events("px"))
    query = next(event for event in events if event.name == "query")
    assert query.data["hyde"].startswith("Đoạn văn")


def test_generate_answer_stream_uses_printer(settings):
    printed: list[str] = []
    chat = FakeChatModel(chunks=["xin ", "chào"])
    service = GenerationService(settings, FakeRetriever(_hits()), chat_model=chat)
    answer = service.generate_answer_stream("hi", printer=printed.append)
    assert answer == "xin chào"
    assert "".join(printed) == "xin chào"


def test_empty_hits_fallback_skips_llm(settings):
    chat = FakeChatModel("Không đủ ngữ cảnh.")
    service = GenerationService(settings, FakeRetriever([]), chat_model=chat)
    answer = service.generate_answer("câu hỏi không có tài liệu")
    assert "Không đủ học liệu" in answer
    assert "bịa" in answer
    assert chat.invoked == []


def test_low_cosine_fallback_skips_llm(settings):
    hits = [
        RetrievalResult(
            id="1",
            score=0.03,
            content_type="text",
            content=" unrelated ",
            metadata={
                "relative_path": "assets/hethongquytrinhnghiepvu/chap01.pdf",
                "cosine": 0.03,
            },
        )
    ]
    chat = FakeChatModel("should not run")
    service = GenerationService(settings, FakeRetriever(hits), chat_model=chat)
    answer = service.generate_answer("Tạo lộ trình môn quy trình nghiệp vụ")
    assert "Không đủ học liệu" in answer
    assert chat.invoked == []
    service = GenerationService(settings, FakeRetriever(_hits()), chat_model=FakeChatModel())
    try:
        service.generate_answer("   ")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_uses_generation_k(settings):
    retriever = FakeRetriever(_hits())
    service = GenerationService(settings, retriever, chat_model=FakeChatModel("ok"))
    service.generate_answer("quan hệ")
    assert retriever.calls[0][1] == max(settings.retriever_k, settings.generation_k)
    service.generate_answer("quan hệ", k=3, include_visual=False)
    assert retriever.calls[1][1] == 3
    assert retriever.calls[1][2] is False


def test_injected_model_does_not_load_causal_lm(settings, monkeypatch):
    def boom(self):
        raise AssertionError("AutoModelForCausalLM should not load")

    monkeypatch.setattr(GenerationService, "_ensure_loaded", boom)
    chat = FakeChatModel("ok")
    service = GenerationService(settings, FakeRetriever(_hits()), chat_model=chat)
    assert service.generate_answer("quan hệ") == "ok"
    visible = "".join(service.iter_answer_tokens("quan hệ"))
    assert visible == "ok"


def test_enhance_keeps_original_question_and_passes_planner(settings):
    settings.query_enhance = True
    enhance_json = (
        '{"rewritten":"quan hệ phản xạ và đối xứng",'
        '"subqueries":["quan hệ phản xạ","quan hệ đối xứng"],'
        '"step_back":"quan hệ hai ngôi"}'
    )
    chat = FakeChatModel("ok", enhance_text=enhance_json)
    retriever = FakeRetriever(_hits())
    service = GenerationService(settings, retriever, chat_model=chat)
    answer = service.generate_answer("px vs dx giúp với")
    assert answer == "ok"
    assert chat.invoked[0]["enhance"] is True
    payload = chat.invoked[1]
    assert payload["question"] == "px vs dx giúp với"
    assert payload["context"]
    enhanced = retriever.calls[0][3]
    assert enhanced is not None
    assert enhanced.rewritten == "quan hệ phản xạ và đối xứng"
    assert enhanced.subqueries == ["quan hệ phản xạ", "quan hệ đối xứng"]
    assert enhanced.step_back == "quan hệ hai ngôi"
    assert service.last_enhanced is enhanced


def test_no_enhance_skips_planner(settings):
    chat = FakeChatModel("ok", enhance_text='{"rewritten":"should not run"}')
    retriever = FakeRetriever(_hits())
    service = GenerationService(settings, retriever, chat_model=chat)
    service.generate_answer("quan hệ", enhance=False)
    assert all(not (isinstance(p, dict) and p.get("enhance")) for p in chat.invoked)
    assert retriever.calls[0][3] is None
    assert service.last_enhanced is None


def test_generate_passes_source_and_course_to_retriever(settings):
    retriever = FakeRetriever(_hits())
    service = GenerationService(settings, retriever, chat_model=FakeChatModel("ok"))
    service.generate_answer(
        "quan hệ",
        enhance=False,
        source="buoi_3.mp4",
        course="test",
        content_type="text",
    )
    assert retriever.calls[0][4] == "buoi_3.mp4"
    assert retriever.calls[0][5] == "test"
    assert retriever.calls[0][6] == "text"


def test_enhance_temporarily_sets_max_new_tokens(settings):
    settings.query_enhance_max_new_tokens = 256

    class Cfg:
        max_new_tokens = 4096

    class Chat:
        def __init__(self) -> None:
            self.cfg = Cfg()
            self.seen: list[int] = []
            self.llm = type("L", (), {})()
            self.llm.pipeline = type("P", (), {})()
            self.llm.pipeline.model = type("M", (), {})()
            self.llm.pipeline.model.generation_config = self.cfg

        def invoke(self, payload):
            self.seen.append(self.cfg.max_new_tokens)
            return '{"rewritten":"r","subqueries":[],"step_back":""}'

    chat = Chat()
    service = GenerationService(settings, FakeRetriever(_hits()))
    service._chat = chat
    service._injected = False
    raw = service._invoke_enhancer("px")
    assert "rewritten" in raw
    assert chat.seen == [256]
    assert chat.cfg.max_new_tokens == 4096


def test_hyde_attaches_paragraph_without_replacing_queries(settings):
    settings.query_hyde = True
    chat = FakeChatModel("ok", hyde_text="Đoạn văn về quan hệ phản xạ trong giáo trình.")
    retriever = FakeRetriever(_hits())
    service = GenerationService(settings, retriever, chat_model=chat)
    answer = service.generate_answer("px", enhance=False)
    assert answer == "ok"
    assert any(isinstance(p, dict) and p.get("hyde") for p in chat.invoked)
    enhanced = retriever.calls[0][3]
    assert enhanced is not None
    assert enhanced.original == "px"
    assert enhanced.hyde.startswith("Đoạn văn")
    assert enhanced.hyde not in enhanced.text_search_queries()


def test_retrieve_loop_merges_follow_up_and_repeats_retrieving(settings):
    settings.max_retrieve_loops = 1
    first = _hits()[0]
    extra = RetrievalResult(
        id="loop",
        score=0.7,
        content_type="text",
        content="quan hệ đối xứng",
        metadata={"relative_path": "assets/test/Chuong_3_quan_he.pptx", "cosine": 0.4},
    )

    class LoopRetriever(FakeRetriever):
        def search(self, raw_query, k=None, include_visual=True, *, enhanced=None, source=None, course=None, content_type=None):
            self.calls.append((raw_query, k, include_visual, enhanced, source, course, content_type))
            if len(self.calls) == 1:
                return [first]
            return [extra]

    chat = FakeChatModel(
        "ok",
        chunks=["ok"],
        reflect_text='{"needs_more":true,"follow_up":"quan hệ đối xứng"}',
    )
    retriever = LoopRetriever()
    service = GenerationService(settings, retriever, chat_model=chat)
    events = list(service.iter_ask_events("quan hệ", enhance=False))
    stages = [e.data.get("stage") for e in events if e.name == "status"]
    assert stages[:2] == ["retrieving", "retrieving"]
    assert service.last_retrieve_loops == 1
    assert {hit.id for hit in service.last_hits} == {"1", "loop"}
    assert retriever.calls[1][0] == "quan hệ đối xứng"
