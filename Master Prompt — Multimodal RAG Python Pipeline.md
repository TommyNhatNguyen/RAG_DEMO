# Build a Production-Ready Multimodal RAG Pipeline in Python

## 1. Objective

Build a modular Python multimodal RAG ingestion and retrieval system that accepts:

- PDF
- DOCX
- PPTX
- TXT
- Markdown
- Images
- Videos

The system must process these inputs, extract their text/visual content, generate embeddings, index them into ChromaDB, and provide a retrieval API that can later be connected to an LLM for answer generation.

I am currently using:

- Python
- Docling
- LangChain
- ChromaDB
- Hugging Face models

Do not replace these technologies unless there is a strong technical reason.

The implementation should be modular so that individual components can later be replaced.

---

# 2. High-Level Architecture

Implement this architecture:

```text
                            INPUT
                              |
                 +------------+------------+
                 |            |            |
                PDF          DOCX/PPTX    TXT/MD
                 |            |            |
                 +------------+------------+
                              |
                           Docling
                              |
                 +------------+-------------+
                 |                          |
             Text content             Visual content
                 |                          |
                 |                    Images / Pages
                 |                          |
                 |                          |
                 v                          v
        Text Chunking                Image Processing
                 |                          |
                 v                          v
        Qwen3-Embedding          Qwen3-VL-Embedding
                 |                          |
                 +------------+-------------+
                              |
                              |
                            ChromaDB
                              |
                              |
                              v
                           Retrieval
                              |
                    +---------+---------+
                    |                   |
               Text results       Visual results
                    |                   |
                    +---------+---------+
                              |
                           Reranker
                              |
                              v
                             LLM
                              |
                              v
                            Answer
```

For video:

```text
Video
 |
 +---------------------+
 |                     |
 v                     v
FFmpeg/OpenCV       FFmpeg audio
 |                     |
 v                     v
Frames            faster-whisper
 |                     |
 |                     v
 |                Transcript
 |                     |
 +----------+----------+
            |
            v
      Video segments
            |
            v
   Qwen3-VL-Embedding
            |
            v
         ChromaDB
```

---

# 3. Important Architectural Principles

## 3.1 Separate ingestion from retrieval

The project must have two major subsystems:

```text
ingestion/
retrieval/
```

Do not tightly couple ingestion and retrieval.

---

## 3.2 Do not treat every file as plain text

The system must preserve:

- text
- images
- tables
- page information
- document structure
- video timestamps
- source metadata

Do not simply convert every document into Markdown and discard the original structure.

---

## 3.3 OCR is preprocessing, not embedding

Use OCR when a document/image contains text that cannot be extracted from the native text layer.

Tesseract is an OCR engine.

It must NOT be treated as an embedding model.

Conceptually:

```text
Image
  |
  v
Tesseract OCR
  |
  v
Text
  |
  v
Qwen3-Embedding
```

while the original image can independently go through:

```text
Image
  |
  v
Qwen3-VL-Embedding
```

Therefore, when useful, preserve both representations.

---

# 4. Technology Stack

Use the following technologies.

## Document processing

### Docling

Use Docling as the primary document processing framework for:

- PDF
- DOCX
- PPTX
- images when appropriate
- structured document extraction

Do not use PyPDF as the primary parser.

Important:

`pypdf` and `pypdfium2` are different libraries.

Docling's PDF processing should use its supported PDF backends.

Do not introduce `pypdf` unless there is a specific feature that Docling cannot provide.

---

# 5. OCR

Use:

```text
Tesseract OCR
```

as the initial OCR implementation.

OCR should be used for:

- scanned PDFs
- scanned documents
- screenshots
- images containing text
- pages without a usable text layer

Do not OCR every document unnecessarily.

The pipeline should prefer native text extraction when available.

Conceptually:

```python
if native_text_available:
    use_native_text()
else:
    use_ocr()
```

Design OCR behind an interface so that it can later be replaced by:

- RapidOCR
- PaddleOCR
- another OCR model
- Docling-supported OCR engines

---

# 6. Image Processing

Use:

```text
Pillow
```

for basic image processing.

Normalize images to RGB when necessary.

Do not resize/compress images unnecessarily before embedding.

Preserve the original image when possible.

Store processed images outside ChromaDB and store only references/paths/URLs in metadata.

---

# 7. Video Processing

Use:

```text
FFmpeg
OpenCV
faster-whisper
```

Responsibilities:

### FFmpeg

Use for:

- extracting audio
- extracting frames
- obtaining video metadata
- converting media formats

### OpenCV

Use for:

- frame processing
- frame sampling
- optional scene/frame analysis

### faster-whisper

Use for:

- speech-to-text transcription
- transcript timestamps

Do not create an embedding for every video frame.

---

# 8. Video Segmentation

A video must be divided into meaningful segments.

Example:

```text
video.mp4

00:00 - 00:15
00:15 - 00:30
00:30 - 00:45
...
```

Each segment should contain:

```python
VideoSegment(
    video_id,
    start_time,
    end_time,
    transcript,
    frame_paths
)
```

Frame sampling must be configurable.

For example:

```text
frames_per_segment = 3
segment_duration = 15 seconds
```

These should be configuration values, not hardcoded.

---

# 9. Embedding Models

Use Hugging Face models.

## Text

Use:

```text
Qwen/Qwen3-Embedding-0.6B
```

as the default development model.

Make the model configurable so it can later be changed to:

```text
Qwen/Qwen3-Embedding-4B
Qwen/Qwen3-Embedding-8B
```

without changing application code.

---

## Multimodal

Use:

```text
Qwen/Qwen3-VL-Embedding-2B
```

as the default development model.

Make it configurable so it can later be changed to:

```text
Qwen/Qwen3-VL-Embedding-8B
```

The multimodal model should support visual representations such as:

- images
- screenshots
- video frames
- video segments
- optionally text + image/video combinations where appropriate

---

# 10. Important Embedding Design

Do not assume that:

```text
Qwen3-Embedding
```

and:

```text
Qwen3-VL-Embedding
```

can automatically be placed into the same vector space.

Implement the system so that embedding collections can be separated.

Recommended initial design:

```text
ChromaDB
 |
 +-- text_collection
 |
 +-- visual_collection
```

Where:

```text
text_collection
    |
    +-- PDF text
    +-- DOCX text
    +-- PPTX text
    +-- TXT
    +-- Markdown
    +-- OCR text
```

and:

```text
visual_collection
    |
    +-- images
    +-- PDF page images
    +-- document images
    +-- PPT slides
    +-- video frames
    +-- video segments
```

However, design the abstraction so that a future unified multimodal collection using Qwen3-VL-Embedding can be enabled without rewriting the application.

---

# 11. Document Representation

Create strongly typed internal models using Pydantic/dataclasses.

At minimum implement:

```python
DocumentAsset
TextChunk
ImageAsset
TableAsset
VideoAsset
VideoSegment
EmbeddingRecord
```

Example:

```python
class TextChunk:
    id: str
    document_id: str
    text: str
    page_number: int | None
    section: str | None
    chunk_index: int
    metadata: dict
```

Example:

```python
class ImageAsset:
    id: str
    document_id: str
    path: str
    page_number: int | None
    caption: str | None
    metadata: dict
```

Example:

```python
class VideoSegment:
    id: str
    video_id: str
    start_time: float
    end_time: float
    transcript: str
    frame_paths: list[str]
    metadata: dict
```

---

# 12. Metadata Design

Every indexed item must have rich metadata.

At minimum:

```json
{
  "document_id": "...",
  "source": "...",
  "file_name": "...",
  "file_type": "...",
  "content_type": "text|image|table|video|video_segment|page",
  "page_number": 1,
  "section": "...",
  "chunk_index": 0
}
```

For video:

```json
{
  "content_type": "video_segment",
  "video_id": "...",
  "start_time": 120.0,
  "end_time": 135.0
}
```

For images:

```json
{
  "content_type": "image",
  "image_path": "...",
  "page_number": 10
}
```

Metadata must make it possible to reconstruct where the retrieved content came from.

This is required for future citations.

---

# 13. Object Storage

Do NOT store large binary files directly inside ChromaDB.

Use filesystem storage initially:

```text
storage/
    documents/
    images/
    videos/
    frames/
    audio/
```

ChromaDB should store:

```text
embedding
document/text
metadata
path/reference
```

Later the storage abstraction should be replaceable with:

```text
S3
MinIO
Cloudinary
```

without changing the embedding/retrieval layer.

---

# 14. ChromaDB

Use persistent ChromaDB.

Example concept:

```python
client = chromadb.PersistentClient(
    path="./data/chroma"
)
```

Create separate collections initially:

```text
text_embeddings
visual_embeddings
```

Use cosine similarity unless there is a strong reason to use another metric.

The ChromaDB layer must be encapsulated behind a repository class.

For example:

```python
class VectorStore:
    def add(...)
    def search(...)
    def delete(...)
    def get(...)
```

Do not scatter direct ChromaDB calls throughout the application.

---

# 15. LangChain

Continue using LangChain where it provides useful abstractions.

Use it primarily for:

- document abstractions
- text splitting
- retrievers
- retrieval chains
- LLM integration

Do NOT make the entire ingestion system dependent on LangChain abstractions.

The lower-level ingestion pipeline should remain usable without LangChain.

---

# 16. Text Chunking

Use LangChain text splitters where appropriate.

Start with:

```python
RecursiveCharacterTextSplitter
```

with configurable:

```text
chunk_size
chunk_overlap
```

However, preserve document structure.

Prefer:

```text
document
  |
  section
    |
    paragraph
      |
      chunk
```

rather than blindly splitting the entire document.

The chunk should preserve:

- page
- heading/section
- document ID
- source
- chunk index

---

# 17. Tables

Do not blindly convert tables to normal text.

Represent tables separately when possible.

For example:

```text
Table
 |
 +-- page
 +-- rows
 +-- columns
 +-- markdown representation
 +-- optional rendered image
```

A table can have:

```text
text representation
```

and optionally:

```text
visual representation
```

depending on the retrieval strategy.

---

# 18. PDF Processing

For PDF:

```text
PDF
 |
 v
Docling
 |
 +-- native text
 |
 +-- tables
 |
 +-- images
 |
 +-- pages
 |
 +-- OCR if required
```

Do not use:

```text
PDF -> pypdf -> plain text
```

as the primary pipeline.

The goal is to preserve document structure.

---

# 19. DOCX Processing

Use Docling:

```text
DOCX
 |
 v
Docling
 |
 +-- paragraphs
 +-- headings
 +-- tables
 +-- images
```

Then:

```text
text -> Qwen3-Embedding
images -> Qwen3-VL-Embedding
```

---

# 20. PPTX Processing

Use Docling:

```text
PPTX
 |
 v
Docling
 |
 +-- slide text
 +-- slide structure
 +-- tables
 +-- images
```

Treat each slide as a meaningful unit.

For example:

```text
slide_001
slide_002
slide_003
```

Each slide should preserve:

```text
presentation_id
slide_number
title
text
images
```

Optionally render the entire slide to an image and use:

```text
Qwen3-VL-Embedding
```

for visual retrieval.

---

# 21. TXT / Markdown

For TXT and Markdown:

```text
TXT/MD
 |
 v
Text loader
 |
 v
Chunking
 |
 v
Qwen3-Embedding
 |
 v
ChromaDB
```

Markdown headings should be preserved as section metadata when possible.

---

# 22. Image Input

For a standalone image:

```text
image
 |
 +--> Qwen3-VL-Embedding
 |
 +--> optional OCR
          |
          v
     Qwen3-Embedding
```

Use both when useful.

Example:

```text
screenshot.png
```

could produce:

```text
Visual embedding
+
OCR text embedding
```

This allows retrieval based on both:

- visual semantics
- exact textual content

---

# 23. Retrieval Architecture

Implement retrieval as multiple stages.

```text
User Query
    |
    +---------------------+
    |                     |
    v                     v
Text Embedding      VL Embedding
    |                     |
    v                     v
Text Collection     Visual Collection
    |                     |
    +----------+----------+
               |
               v
          Merge results
               |
               v
            Rerank
               |
               v
         Top K contexts
```

The retrieval layer should return a common object:

```python
class RetrievalResult:
    id: str
    score: float
    content_type: str
    content: str | None
    metadata: dict
```

---

# 24. Reranking

Design the architecture so that reranking is a separate component.

Possible future models:

```text
Qwen3-Reranker
Qwen3-VL-Reranker
```

Do not tightly couple retrieval to reranking.

Implement:

```python
class Reranker:
    def rerank(
        self,
        query,
        results
    ):
        ...
```

Initially, a simple score-based ranking implementation is acceptable if the reranker model is not yet implemented.

---

# 25. Query Types

The retrieval system should eventually support:

### Text query

```text
"What was the company's revenue in 2025?"
```

### Visual query

```text
"Find the chart showing revenue growth."
```

### Cross-modal query

```text
"Find the slide containing a diagram explaining the architecture."
```

### Video query

```text
"Find where the speaker explains database indexing."
```

The architecture should not assume every query is purely textual.

---

# 26. Project Structure

Create this project structure:

```text
multimodal-rag/
│
├── app/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   │
│   ├── models/
│   │   ├── document.py
│   │   ├── chunk.py
│   │   ├── image.py
│   │   ├── video.py
│   │   └── retrieval.py
│   │
│   ├── loaders/
│   │   ├── base.py
│   │   ├── docling_loader.py
│   │   ├── image_loader.py
│   │   └── video_loader.py
│   │
│   ├── processors/
│   │   ├── ocr.py
│   │   ├── image.py
│   │   ├── video.py
│   │   └── audio.py
│   │
│   ├── chunking/
│   │   ├── text_chunker.py
│   │   └── video_chunker.py
│   │
│   ├── embeddings/
│   │   ├── base.py
│   │   ├── text_embedding.py
│   │   └── vl_embedding.py
│   │
│   ├── vectorstore/
│   │   ├── base.py
│   │   └── chroma.py
│   │
│   ├── retrieval/
│   │   ├── retriever.py
│   │   ├── reranker.py
│   │   └── merger.py
│   │
│   ├── pipeline/
│   │   ├── ingestion.py
│   │   └── indexing.py
│   │
│   └── main.py
│
├── storage/
│   ├── documents/
│   ├── images/
│   ├── videos/
│   ├── frames/
│   └── audio/
│
├── data/
│   └── chroma/
│
├── tests/
│
├── .env.example
├── pyproject.toml
├── README.md
└── docker-compose.yml
```

---

# 27. Configuration

Use environment variables and a typed settings class.

Example:

```text
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
VL_EMBEDDING_MODEL=Qwen/Qwen3-VL-Embedding-2B

CHROMA_PATH=./data/chroma

TEXT_COLLECTION=text_embeddings
VISUAL_COLLECTION=visual_embeddings

OCR_ENGINE=tesseract

VIDEO_SEGMENT_DURATION=15
VIDEO_FRAMES_PER_SEGMENT=3

CHUNK_SIZE=1000
CHUNK_OVERLAP=150

DEVICE=mps
```

Do not hardcode these values.

---

# 28. Device Support

The system must support:

```text
cpu
cuda
mps
```

My development environment is:

```text
MacBook Pro M1
16 GB RAM
```

Therefore:

```text
DEVICE=mps
```

must work where supported.

Do not assume CUDA.

The implementation should gracefully fall back to CPU.

---

# 29. Model Loading

Models must be loaded once and reused.

Do NOT do this:

```python
def embed(text):
    model = load_model()
    return model.embed(text)
```

Instead:

```python
embedding_service = EmbeddingService(...)
```

and keep the model alive.

This is important for performance.

---

# 30. Batch Embedding

Implement batch embedding.

Do not embed one item at a time when large numbers of chunks are available.

For example:

```python
embed_documents(
    documents,
    batch_size=8
)
```

Make batch size configurable.

---

# 31. Incremental Indexing

The pipeline must support incremental ingestion.

If:

```text
document.pdf
```

has already been indexed, do not reprocess it unnecessarily.

Use a deterministic ID/hash.

For example:

```text
SHA-256(file)
```

Generate IDs based on:

```text
document_hash
+
chunk_index
+
content_type
```

If a document changes, detect the new hash and re-index it.

---

# 32. Idempotency

Running:

```bash
python -m app.main ingest document.pdf
```

multiple times should NOT create duplicate vectors.

The indexing operation must be idempotent.

---

# 33. Error Handling

Failures in one file must not crash the entire ingestion batch.

Example:

```text
100 files
 |
 +-- 98 successful
 +-- 2 failed
```

The system should report:

```text
success = 98
failed = 2
```

and record the errors.

Do not silently swallow exceptions.

---

# 34. Logging

Use Python's standard logging framework.

Log:

```text
file detected
loader selected
document parsed
OCR executed
chunks generated
images extracted
frames generated
embeddings generated
vectors stored
errors
processing duration
```

Do not log sensitive document contents unnecessarily.

---

# 35. CLI

Implement a CLI.

Examples:

```bash
python -m app.main ingest ./documents
```

```bash
python -m app.main ingest ./documents/file.pdf
```

```bash
python -m app.main search "What is the revenue in 2025?"
```

```bash
python -m app.main stats
```

---

# 36. Example Ingestion API

The ingestion pipeline should conceptually expose:

```python
pipeline = IngestionPipeline(
    loader=...,
    text_embedder=...,
    vl_embedder=...,
    vector_store=...
)

pipeline.ingest(
    "document.pdf"
)
```

Internally:

```text
detect file
    ↓
load
    ↓
extract
    ↓
OCR if required
    ↓
normalize
    ↓
chunk
    ↓
generate embeddings
    ↓
store assets
    ↓
store vectors
```

---

# 37. Example PDF Flow

For:

```text
annual_report.pdf
```

produce:

```text
Document
 |
 +-- TextChunk #1
 |      page=1
 |
 +-- TextChunk #2
 |      page=1
 |
 +-- Table #1
 |      page=3
 |
 +-- Image #1
 |      page=5
 |
 +-- Image #2
        page=10
```

Then:

```text
TextChunk → Qwen3-Embedding
Image → Qwen3-VL-Embedding
```

and index into Chroma.

---

# 38. Example Scanned PDF Flow

For:

```text
scanned_contract.pdf
```

use:

```text
PDF
 ↓
Docling
 ↓
No native text
 ↓
Tesseract
 ↓
OCR text
 ↓
Text chunks
 ↓
Qwen3-Embedding
```

If page images are useful:

```text
page image
 ↓
Qwen3-VL-Embedding
```

Store both.

---

# 39. Example Video Flow

For:

```text
lecture.mp4
```

use:

```text
lecture.mp4
 |
 +--> FFmpeg → audio
 |       |
 |       v
 |   faster-whisper
 |       |
 |       v
 |   transcript
 |
 +--> FFmpeg/OpenCV
         |
         v
       frames
         |
         v
    video segments
         |
         v
 Qwen3-VL-Embedding
         |
         v
      ChromaDB
```

Each result must preserve:

```text
video ID
start timestamp
end timestamp
frame references
transcript
```

---

# 40. Testing

Write unit tests for:

```text
file detection
Docling loader
OCR
image processing
video segmentation
text chunking
embedding
Chroma repository
metadata
ID generation
incremental indexing
retrieval
```

Also create integration tests:

```text
PDF → Docling → embedding → Chroma
```

```text
image → VL embedding → Chroma
```

```text
video → frames/transcript → VL embedding → Chroma
```

Use small test fixtures.

Do not require large models for every unit test.

Mock embedding models in unit tests.

---

# 41. Dependency Management

Use:

```text
pyproject.toml
```

Do not use an unstructured requirements.txt-only setup.

Separate dependencies into groups if appropriate:

```text
core
document
vision
video
development
```

---

# 42. README

Create a comprehensive README containing:

1. Architecture
2. Installation
3. System dependencies
4. Tesseract installation
5. FFmpeg installation
6. Environment variables
7. Model setup
8. Running ingestion
9. Running search
10. ChromaDB structure
11. Supported file formats
12. Troubleshooting
13. Future architecture

For macOS include installation examples such as:

```bash
brew install tesseract
brew install ffmpeg
```

Do not assume Homebrew is mandatory; document alternatives where practical.

---

# 43. Important Non-Goals

Do NOT implement:

- frontend UI
- authentication
- user management
- cloud deployment
- payment
- production Kubernetes
- distributed workers

Keep the scope focused on:

```text
ingestion
processing
embedding
indexing
retrieval
```

---

# 44. Future Extensibility

The architecture must allow future integration of:

```text
S3 / MinIO
PostgreSQL
Redis
Celery / BullMQ
RabbitMQ
Kafka
Qdrant
Milvus
pgvector
```

without rewriting the core pipeline.

Use interfaces/abstractions where they provide genuine value, but do not over-engineer the project.

---

# 45. Final Expected Flow

The final system should support:

```text
PDF
 └── Docling
      ├── text ────────→ Qwen3-Embedding ───────┐
      ├── OCR text ────→ Qwen3-Embedding ───────┤
      ├── table ───────→ text embedding ────────┤
      └── images ──────→ Qwen3-VL-Embedding ────┤
                                                  │
DOCX ──→ Docling ────────────────────────────────┤
PPTX ──→ Docling ────────────────────────────────┤
TXT ───→ Text chunking → Qwen3-Embedding ────────┤
MD ────→ Text chunking → Qwen3-Embedding ────────┤
                                                  │
Image ─→ Pillow ─→ Qwen3-VL-Embedding ───────────┤
        └────→ OCR → Qwen3-Embedding ────────────┤
                                                  │
Video ─→ FFmpeg/OpenCV → frames → VL embedding ──┤
      └→ Whisper → transcript → embedding ───────┤
                                                  ▼
                                             ChromaDB
                                                  │
                                                  ▼
                                             Retrieval
                                                  │
                                                  ▼
                                              Reranker
                                                  │
                                                  ▼
                                                 LLM
```

---

# 46. Implementation Requirements

Before writing code:

1. Inspect the current repository.
2. Identify existing Docling/LangChain code.
3. Do not unnecessarily rewrite existing working code.
4. Propose the migration/implementation plan.
5. Then implement incrementally.
6. Keep components independently testable.
7. Use type hints throughout.
8. Use Pydantic models for external/configuration data.
9. Use dependency injection where appropriate.
10. Avoid global mutable state.
11. Avoid hardcoded model paths.
12. Do not hardcode device = CUDA.
13. Support MPS/CPU.
14. Make model names configurable.
15. Make chunking/video/OCR settings configurable.
16. Preserve source metadata.
17. Make indexing idempotent.
18. Add tests.
19. Update README.
20. Run the tests before considering the implementation complete.

---

# 47. Important Decision

Do not prematurely implement a single unified multimodal Chroma collection.

Start with:

```text
text_embeddings
visual_embeddings
```

because Qwen3-Embedding and Qwen3-VL-Embedding may represent different embedding spaces.

However, design the embedding/vector-store interfaces so that the system can later support:

```text
Qwen3-VL-Embedding
        ↓
unified multimodal collection
```

if benchmarking demonstrates that this is the better architecture.

---

# 48. Deliverables

At the end, provide:

1. Complete project structure
2. `pyproject.toml`
3. `.env.example`
4. All Python source files
5. ChromaDB integration
6. Docling integration
7. Tesseract OCR integration
8. Pillow image processing
9. FFmpeg/OpenCV video processing
10. faster-whisper transcription
11. Qwen3-Embedding integration
12. Qwen3-VL-Embedding integration
13. Text and visual collections
14. Retrieval implementation
15. Metadata schema
16. CLI
17. Unit tests
18. Integration tests
19. README
20. Example commands

Do not leave major components as pseudocode.

If a model API differs from the expected API, inspect the current official Hugging Face/model documentation and implement against the actual current API rather than inventing an API.

Prioritize a working, minimal end-to-end pipeline first:

```text
PDF → Docling → text chunks → Qwen3-Embedding → ChromaDB → search
```

Then add:

```text
PDF images → Qwen3-VL-Embedding
```

Then:

```text
standalone images → VL embedding
```

Then:

```text
video → frames + Whisper → VL embedding → ChromaDB
```

Finally integrate multimodal retrieval and reranking.