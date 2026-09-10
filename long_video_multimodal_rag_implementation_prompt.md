# Multimodal RAG — Long Video Processing & Intelligent Frame Sampling Implementation Prompt

## Role

You are a senior Python/AI engineer implementing a production-oriented multimodal RAG ingestion pipeline.

The existing project uses:

- Python
- Docling
- LangChain
- ChromaDB
- Hugging Face models

The system accepts:

- PDF
- DOCX
- PPTX
- TXT
- Markdown
- Images
- Long videos, including 3–4 hour videos

The current problem is that long videos are processed using a maximum video-duration cutoff. This must be replaced with an efficient long-video processing strategy that does **not** embed every frame and does **not** reject/cut off videos simply because they are several hours long.

The goal is:

> Process the entire video, extract its semantic content, select only representative/key frames, embed those selected frames, and index timestamp-aware video segments into ChromaDB.

Do not solve this by simply increasing the maximum video duration.

---

# 1. Primary Objective

Implement a long-video ingestion pipeline:

```text
Long Video
    |
    +-----------------------------+
    |                             |
    v                             v
Audio extraction              Coarse frame sampling
    |                             |
    v                             v
faster-whisper              OpenCV / FFmpeg
    |                             |
    v                             v
Timestamped transcript       Candidate frames
    |                             |
    |                    +--------+--------+
    |                    |                 |
    |                    v                 v
    |              Scene detection    Visual similarity
    |                    |                 |
    |                    +--------+--------+
    |                             |
    |                         OCR change
    |                             |
    +-------------+---------------+
                  |
                  v
        Candidate video segments
                  |
                  v
       Representative frame selection
                  |
                  v
          Qwen3-VL-Embedding
                  |
                  v
              ChromaDB
```

Also embed the transcript using:

```text
Qwen3-Embedding
```

so that video retrieval can work from both:

- spoken/textual content
- visual content

---

# 2. Critical Design Principle

Do NOT do:

```text
4 hour video
    ↓
extract every frame
    ↓
Qwen3-VL-Embedding
    ↓
thousands/tens of thousands of embeddings
```

Do NOT do:

```text
video duration > MAX_DURATION
    ↓
truncate/reject video
```

Instead:

```text
4 hour video
    ↓
cheap coarse analysis
    ↓
detect meaningful changes
    ↓
select representative frames
    ↓
expensive VL embedding only for selected frames
```

The expensive model must only process selected frames.

---

# 3. Target Technology Stack

Use:

| Task | Technology |
|---|---|
| Video metadata | FFprobe / FFmpeg |
| Video decoding | FFmpeg |
| Frame processing | OpenCV |
| Scene detection | PySceneDetect |
| Image processing | Pillow |
| OCR | Tesseract initially |
| Speech-to-text | faster-whisper |
| Text embedding | Qwen3-Embedding |
| Visual embedding | Qwen3-VL-Embedding |
| Optional clustering | scikit-learn |
| Vector database | ChromaDB |
| RAG orchestration | LangChain |
| Configuration | Pydantic Settings |
| Testing | pytest |

Do not replace the existing Docling/LangChain/Chroma architecture unnecessarily.

---

# 4. Important Scope

This task is specifically about:

1. Long-video processing
2. Efficient frame selection
3. Timestamped segmentation
4. Transcript extraction
5. Visual embedding
6. Text embedding
7. ChromaDB indexing
8. Retrieval-ready metadata

Do not implement:

- frontend
- authentication
- billing
- user management
- cloud deployment
- Kubernetes
- distributed workers

unless they already exist and are required to preserve compatibility.

---

# 5. Existing Architecture Compatibility

Inspect the existing repository before making changes.

First identify:

- current project structure
- current video processing implementation
- current Docling integration
- current LangChain integration
- current embedding implementation
- current ChromaDB implementation
- current configuration
- current tests
- current video duration cutoff

Do not rewrite working components unnecessarily.

Find and remove/replace logic equivalent to:

```python
if video_duration > MAX_VIDEO_DURATION:
    raise ...
```

or:

```python
video = video[:MAX_DURATION]
```

The new implementation must support videos longer than 3–4 hours.

If a safety/resource limit is still needed, it must be configurable and must not silently truncate the video.

---

# 6. Project Structure

Add or adapt the following structure:

```text
app/
├── config/
│   └── settings.py
│
├── models/
│   ├── video.py
│   ├── transcript.py
│   ├── frame.py
│   └── retrieval.py
│
├── processors/
│   ├── video_metadata.py
│   ├── video_audio.py
│   ├── video_frames.py
│   ├── scene_detection.py
│   ├── frame_similarity.py
│   ├── ocr.py
│   └── video_segmenter.py
│
├── transcription/
│   └── whisper.py
│
├── embeddings/
│   ├── text_embedding.py
│   └── vl_embedding.py
│
├── vectorstore/
│   └── chroma.py
│
├── pipeline/
│   └── video_ingestion.py
│
├── retrieval/
│   └── video_retriever.py
│
└── main.py

storage/
├── videos/
├── audio/
├── frames/
└── thumbnails/

data/
└── chroma/

tests/
├── processors/
├── transcription/
├── embeddings/
├── vectorstore/
└── pipeline/
```

Adapt this to the existing repository instead of blindly creating duplicates.

---

# 7. Configuration

Create typed configuration.

Use environment variables.

Example:

```env
VIDEO_COARSE_SAMPLE_INTERVAL=10

VIDEO_SEGMENT_DURATION=30

VIDEO_MIN_SEGMENT_DURATION=10

VIDEO_MAX_SEGMENT_DURATION=120

VIDEO_FRAMES_PER_SEGMENT=2

VIDEO_MAX_REPRESENTATIVE_FRAMES=3

VIDEO_SCENE_THRESHOLD=27.0

VIDEO_FRAME_SIMILARITY_THRESHOLD=0.90

VIDEO_OCR_ENABLED=true

VIDEO_OCR_INTERVAL=30

VIDEO_MAX_CANDIDATE_FRAMES_PER_SEGMENT=10

WHISPER_MODEL=small

EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B

VL_EMBEDDING_MODEL=Qwen/Qwen3-VL-Embedding-2B

EMBEDDING_BATCH_SIZE=8

DEVICE=mps

CHROMA_PATH=./data/chroma

TEXT_COLLECTION=text_embeddings

VISUAL_COLLECTION=visual_embeddings
```

All values must be configurable.

Do not hardcode them.

---

# 8. Video Metadata

Use FFprobe/FFmpeg to obtain:

- duration
- width
- height
- FPS
- codec
- audio streams
- video streams

Create:

```python
class VideoMetadata:
    video_id: str
    source_path: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    has_audio: bool
```

The entire duration must be processed.

Do not use a maximum-duration cutoff.

---

# 9. Audio Extraction

Extract audio using FFmpeg.

Recommended format:

```text
16 kHz
mono
PCM WAV
```

Conceptually:

```text
video.mp4
    ↓
FFmpeg
    ↓
audio.wav
    ↓
faster-whisper
```

Audio should be stored separately:

```text
storage/audio/{video_id}.wav
```

Avoid extracting audio repeatedly.

If the audio file already exists and the source video hash has not changed, reuse it.

---

# 10. Transcription

Use faster-whisper.

The transcript must include timestamps.

Do NOT only produce:

```text
"The lecturer explains indexing..."
```

Produce:

```python
class TranscriptSegment:
    start_time: float
    end_time: float
    text: str
```

Example:

```json
{
  "start_time": 3720.4,
  "end_time": 3745.8,
  "text": "A B-tree index works by..."
}
```

Store the complete transcript.

---

# 11. Transcript Chunking

Group transcript segments into meaningful video chunks.

Default:

```text
30 seconds
```

but make configurable.

Example:

```text
00:00–00:30
00:30–01:00
01:00–01:30
...
```

Do not blindly split a sentence in the middle.

If a sentence crosses a segment boundary, preserve it.

Each video segment should have:

```python
class VideoSegment:
    id: str
    video_id: str
    start_time: float
    end_time: float
    transcript: str
    transcript_segments: list[TranscriptSegment]
    frame_ids: list[str]
```

---

# 12. Coarse Frame Sampling

Do not decode the entire video at full FPS.

Default:

```text
1 frame every 10 seconds
```

For a 4-hour video:

```text
4 × 60 × 60 / 10
≈ 1440 candidate frames
```

This is acceptable for an initial cheap filtering stage.

Make the interval configurable.

Use FFmpeg or OpenCV efficiently.

Avoid loading the entire video into RAM.

Process frames as a stream.

---

# 13. Frame Storage

Do not store all temporary candidate frames permanently.

Use a temporary directory for coarse candidates.

Example:

```text
tmp/video_id/candidates/
```

After selection:

```text
storage/frames/{video_id}/
```

should contain only selected/representative frames.

Clean up temporary frames after successful indexing.

If processing fails, preserve enough temporary state to resume or retry.

---

# 14. Scene Detection

Use PySceneDetect where appropriate.

Detect:

- hard cuts
- major scene changes

Do not assume scene detection is enough.

For example, a 1-hour lecture may have one visual scene while its PowerPoint changes every few minutes.

Scene detection is one signal, not the only signal.

---

# 15. Visual Similarity

Implement cheap frame similarity.

Possible techniques:

- perceptual hash
- SSIM
- low-resolution pixel difference

Start with a simple method that is fast.

Example:

```text
Frame A
Frame B
Frame C
Frame D
Frame E

A ≈ B ≈ C ≈ D
E is different

keep C
keep E
```

Do not call Qwen3-VL-Embedding for this stage.

The purpose is to remove redundant frames before expensive embedding.

---

# 16. OCR Change Detection

Use Tesseract initially.

OCR should be used as an optional filtering signal.

For screen-heavy videos:

```text
Frame A:
"Introduction"

Frame B:
"Database Index"

Frame C:
"Database Index"

Frame D:
"B-Tree"
```

B and D should be preferred because textual content changed.

Do not run Tesseract on every frame if this becomes expensive.

Use:

```text
VIDEO_OCR_INTERVAL
```

or only OCR frames that already passed visual filtering.

The OCR output can also be stored as metadata.

---

# 17. Representative Frame Selection

This is the core algorithm.

For each video segment:

```text
30-second segment
       |
       +-- candidate frame 1
       +-- candidate frame 2
       +-- candidate frame 3
       +-- ...
       +-- candidate frame N
```

Calculate a score for each candidate.

Start with:

```text
score =
    0.35 * visual_change_score
  + 0.30 * OCR/text_change_score
  + 0.20 * scene_boundary_score
  + 0.15 * temporal_coverage_score
```

Make weights configurable.

The exact weights are starting defaults, not hardcoded assumptions.

Select:

```text
1–3 representative frames per segment
```

depending on segment complexity.

Do not select duplicate/near-duplicate frames.

---

# 18. Temporal Coverage

Do not select all representative frames from the same second.

For a segment:

```text
00:00–00:30
```

and 3 frames:

Bad:

```text
00:01
00:02
00:03
```

Better:

```text
00:05
00:15
00:27
```

unless the visual changes are concentrated at one point.

The algorithm should balance:

- semantic importance
- visual difference
- temporal coverage

---

# 19. Special Handling for Screen/Presentation Videos

Optimize for:

- PowerPoint
- screen recording
- programming tutorials
- online courses
- lectures

For these videos, prioritize OCR/text change detection.

Example:

```text
video
 ↓
coarse sample
 ↓
visual similarity
 ↓
OCR
 ↓
detect slide/screen changes
 ↓
representative frame
```

If OCR text changes substantially, increase the frame's score.

---

# 20. Special Handling for Camera-Only Videos

For talking-head videos:

```text
speaker
speaker
speaker
speaker
```

Do not store hundreds of visually identical frames.

Prefer:

- scene changes
- slide/screen changes
- meaningful visual events

The transcript should carry most of the retrieval signal.

---

# 21. Candidate Selection Algorithm

Implement a deterministic function:

```python
select_representative_frames(
    candidates,
    segment,
    config
) -> list[FrameCandidate]
```

It must:

1. Remove invalid frames.
2. Remove near duplicates.
3. calculate visual change.
4. incorporate OCR change when available.
5. incorporate scene boundaries.
6. maintain temporal coverage.
7. rank candidates.
8. return at most `VIDEO_MAX_REPRESENTATIVE_FRAMES`.

The function must be unit-testable without loading an embedding model.

---

# 22. Qwen3-Embedding

Use:

```text
Qwen/Qwen3-Embedding-0.6B
```

as the default text embedding model.

Use it for:

- transcript chunks
- OCR text
- document text
- video segment transcripts

The model name must be configurable.

Load the model once.

Do not load it for every segment.

Use batching.

---

# 23. Qwen3-VL-Embedding

Use:

```text
Qwen/Qwen3-VL-Embedding-2B
```

as the default visual embedding model.

Use it for selected:

- representative video frames
- document images
- page images
- standalone images

Do not call it on every coarse candidate frame.

The model name must be configurable.

Load it once.

Use batching where supported.

---

# 24. Embedding Video Segments

A video segment should generate:

### Text representation

```text
transcript
```

→ Qwen3-Embedding

### Visual representation

```text
representative frames
```

→ Qwen3-VL-Embedding

Therefore:

```text
VideoSegment
 |
 +-- transcript
 |      ↓
 |  text embedding
 |
 +-- representative frames
        ↓
   VL embeddings
```

---

# 25. Multiple Frames Per Segment

If a segment has:

```text
frame_1
frame_2
frame_3
```

do not automatically create three unrelated retrieval documents.

Prefer:

```text
video_segment_001
    |
    +-- frame_1
    +-- frame_2
    +-- frame_3
```

and preserve all frame IDs in metadata.

If the selected frames need independent visual retrieval, they may also have individual visual vector records.

Support both:

```text
segment-level record
frame-level record
```

if useful.

Do not duplicate unnecessarily.

---

# 26. ChromaDB Schema

Use separate collections initially:

```text
text_embeddings
visual_embeddings
```

because:

```text
Qwen3-Embedding
```

and:

```text
Qwen3-VL-Embedding
```

should not be assumed to share the same vector space.

---

# 27. Text Collection

For each transcript segment:

```python
collection.add(
    ids=[segment_id],
    embeddings=[text_embedding],
    documents=[transcript],
    metadatas=[metadata]
)
```

Metadata:

```json
{
  "content_type": "video_transcript",
  "video_id": "...",
  "source": "...",
  "start_time": 3720.0,
  "end_time": 3750.0,
  "segment_id": "...",
  "frame_ids": "frame1,frame2"
}
```

---

# 28. Visual Collection

For each representative frame:

```python
collection.add(
    ids=[frame_id],
    embeddings=[vl_embedding],
    documents=[""],
    metadatas=[metadata]
)
```

Metadata:

```json
{
  "content_type": "video_frame",
  "video_id": "...",
  "segment_id": "...",
  "frame_id": "...",
  "timestamp": 3742.5,
  "image_path": "...",
  "source": "lecture.mp4"
}
```

---

# 29. Storage Layout

Use:

```text
storage/
├── videos/
│   └── {video_id}.mp4
│
├── audio/
│   └── {video_id}.wav
│
└── frames/
    └── {video_id}/
        ├── {frame_id}.jpg
        └── {frame_id}.jpg
```

Chroma stores references.

Do not store multi-megabyte image binaries inside Chroma metadata.

---

# 30. Video ID

Generate deterministic IDs.

Prefer:

```text
SHA-256(video file)
```

or another stable content hash.

Example:

```python
video_id = sha256(file_bytes)
```

For very large files, stream the hash rather than loading the whole file into memory.

---

# 31. Frame IDs

Use deterministic IDs.

Example:

```text
{video_id}_segment_{segment_index}_frame_{frame_index}
```

or a hash of:

```text
video_id
timestamp
frame content
```

The same video processed twice must not create duplicate records.

---

# 32. Idempotent Indexing

Running:

```bash
python -m app.main ingest video.mp4
```

twice must not duplicate vectors.

If the source hash is unchanged:

```text
skip/reuse existing processing
```

If the source changes:

```text
remove/reindex old records
```

Use Chroma's upsert behavior where appropriate.

---

# 33. Resume Support

Long videos may take a long time to process.

Implement checkpoints.

Suggested stages:

```text
metadata
audio
transcription
coarse_frames
candidate_selection
embedding
indexing
complete
```

Persist status:

```json
{
  "video_id": "...",
  "stage": "candidate_selection",
  "completed": false
}
```

If processing crashes during embedding, it should not need to redo:

- audio extraction
- transcription
- frame extraction

unless necessary.

---

# 34. Progress Reporting

For a 4-hour video, users need progress.

Log:

```text
[1/7] Reading video metadata
[2/7] Extracting audio
[3/7] Transcribing audio: 35%
[4/7] Sampling frames: 50%
[5/7] Selecting representative frames
[6/7] Embedding frames
[7/7] Indexing ChromaDB
```

Include:

- elapsed time
- estimated remaining time when possible
- number of candidate frames
- number of selected frames

Example:

```text
Video duration: 03:58:42
Coarse candidates: 1432
After filtering: 386
Representative frames: 214
Text segments: 478
VL embeddings: 214
```

---

# 35. Performance Metrics

Record:

```text
video_duration
audio_processing_time
transcription_time
frame_sampling_time
frame_filtering_time
ocr_time
embedding_time
chroma_indexing_time
total_time
candidate_frame_count
selected_frame_count
compression_ratio
```

Example:

```text
Frame reduction:
1432 candidates
→ 214 selected
→ 85.1% reduction
```

This lets us measure whether the optimization actually works.

---

# 36. Memory Requirements

Do not load:

```text
entire 4-hour video
```

into memory.

Do not load:

```text
all candidate frames
```

into memory simultaneously.

Process incrementally.

Use:

```text
generator
streaming
temporary files
batches
```

where appropriate.

---

# 37. FFmpeg Requirements

The application must verify FFmpeg availability.

If FFmpeg is missing, produce a clear error:

```text
FFmpeg is required for long-video processing.
Install FFmpeg and ensure it is available on PATH.
```

Do not fail with an obscure subprocess error.

---

# 38. Tesseract Requirements

If OCR is enabled, verify Tesseract.

If unavailable:

- log a clear warning
- either fail fast if OCR is required
- or disable OCR and continue using visual similarity

Make this behavior configurable.

Example:

```env
OCR_REQUIRED=false
```

---

# 39. OCR Should Not Block the Whole Pipeline

If Tesseract fails for a frame:

```text
do not abort the entire video
```

Log the error and continue.

The frame can still be evaluated using visual signals.

---

# 40. Retrieval

Implement a video retriever.

For a user query:

```text
"Where does the lecturer explain B-tree indexing?"
```

perform:

```text
Query
 |
 +--> Qwen3-Embedding
 |        |
 |        v
 |   text_embeddings
 |
 +--> Qwen3-VL-Embedding
          |
          v
     visual_embeddings
```

Merge the results.

Return:

```python
class VideoRetrievalResult:
    video_id: str
    segment_id: str
    start_time: float
    end_time: float
    transcript: str
    frame_paths: list[str]
    score: float
```

---

# 41. Retrieval Result Example

The retriever should return something like:

```json
{
  "video_id": "lecture_001",
  "segment_id": "lecture_001_segment_124",
  "start_time": 3720.0,
  "end_time": 3750.0,
  "transcript": "The B-tree index organizes...",
  "frame_paths": [
    "storage/frames/lecture_001/frame_3725.jpg"
  ],
  "score": 0.91
}
```

This allows the final LLM layer to cite:

```text
01:02:00–01:02:30
```

rather than only returning an image.

---

# 42. Optional Reranking

Keep reranking separate.

Future support:

```text
Qwen3-Reranker
Qwen3-VL-Reranker
```

Architecture:

```text
Retriever
    ↓
Top 20–50 candidates
    ↓
Reranker
    ↓
Top 5–10
```

Do not embed reranking into frame selection.

They solve different problems.

---

# 43. Frame Selection vs Embedding

Keep these concepts strictly separate.

### Frame selection

Goal:

```text
Which frames are worth processing?
```

Use cheap techniques:

- sampling
- scene detection
- pixel similarity
- SSIM
- perceptual hash
- OCR

### Embedding

Goal:

```text
What does this selected frame mean semantically?
```

Use:

```text
Qwen3-VL-Embedding
```

Do not use the expensive embedding model to decide whether every frame is redundant.

---

# 44. Recommended Initial Parameters

Start with:

```env
VIDEO_COARSE_SAMPLE_INTERVAL=10

VIDEO_SEGMENT_DURATION=30

VIDEO_FRAMES_PER_SEGMENT=2

VIDEO_MAX_REPRESENTATIVE_FRAMES=3

VIDEO_SCENE_THRESHOLD=27.0

VIDEO_FRAME_SIMILARITY_THRESHOLD=0.90

VIDEO_OCR_ENABLED=true

VIDEO_OCR_INTERVAL=30

VIDEO_MAX_CANDIDATE_FRAMES_PER_SEGMENT=10

EMBEDDING_BATCH_SIZE=8
```

These are starting values.

Do not assume they are optimal for every video.

The implementation must make them easy to benchmark.

---

# 45. Example 4-Hour Video

For a 4-hour video:

```text
Duration:
14,400 seconds
```

At:

```text
1 frame / 10 sec
```

we get approximately:

```text
1,440 candidates
```

After visual/OCR filtering:

```text
~300–500 candidates
```

After representative selection:

```text
~150–300 frames
```

Then:

```text
~150–300 VL embeddings
```

instead of:

```text
14,400+
```

The exact number depends on the content.

The pipeline must report the actual numbers rather than assuming them.

---

# 46. Avoid Over-Optimization

Do not immediately introduce:

- GPU-based video decoding
- distributed processing
- Kafka
- Celery
- Ray
- Kubernetes
- complex vision models

The first implementation should use:

```text
FFmpeg
OpenCV
PySceneDetect
Tesseract
faster-whisper
Qwen embeddings
ChromaDB
```

and establish a measurable baseline.

Only optimize further after profiling.

---

# 47. Benchmark Mode

Add a benchmark command:

```bash
python -m app.main benchmark-video ./video.mp4
```

Output:

```text
Video:
Duration: 03:58:42

Sampling:
Interval: 10 sec
Candidates: 1432

Filtering:
Visual duplicates removed: 612
OCR-filtered candidates: 380

Representative frames:
214

Reduction:
85.1%

Processing:
Transcription: 12m 32s
Frame analysis: 1m 15s
OCR: 2m 40s
VL embedding: 3m 11s
Chroma indexing: 15s

Total:
19m 53s
```

The benchmark must make it easy to compare different sampling strategies.

---

# 48. A/B Sampling Strategies

Design the code so we can compare:

### Strategy A

```text
uniform 10-second sampling
```

### Strategy B

```text
scene detection
```

### Strategy C

```text
scene + visual similarity
```

### Strategy D

```text
scene + visual similarity + OCR
```

### Strategy E

```text
scene + visual similarity + OCR + transcript-aware selection
```

The architecture should allow different strategies behind:

```python
FrameSelectionStrategy
```

---

# 49. Strategy Interface

Create:

```python
class FrameSelectionStrategy(Protocol):
    def select(
        self,
        candidates: list[FrameCandidate],
        segments: list[VideoSegment],
    ) -> list[FrameCandidate]:
        ...
```

Implement:

```text
UniformSamplingStrategy
VisualSimilarityStrategy
SemanticFrameSelectionStrategy
```

The default should be:

```text
SemanticFrameSelectionStrategy
```

using cheap visual + OCR + scene + temporal signals.

---

# 50. Transcript-Aware Selection

Use transcript content to prioritize visually meaningful moments.

Example:

```text
Transcript:
"Now let's look at the architecture diagram."
```

The frames around this timestamp should receive a higher priority.

However, do NOT use an LLM to score every transcript sentence.

That would defeat the purpose of optimization.

Use cheap heuristics initially:

- sentence density
- keyword signals
- transcript segment boundaries
- long pauses
- topic boundaries when available

Later, an LLM can optionally be used only for higher-level segment selection.

---

# 51. Optional Future Semantic Stage

Design the architecture so an optional semantic selector can be added:

```text
Candidate frames
      +
Transcript
      ↓
Small VLM / LLM
      ↓
Select top semantic frames
```

But this must be optional.

Do not make an expensive LLM call for every frame in the initial implementation.

---

# 52. Error Handling

Each stage must have explicit errors.

Examples:

```text
VideoMetadataError
AudioExtractionError
TranscriptionError
FrameExtractionError
OCRError
EmbeddingError
VectorStoreError
```

Do not silently catch everything.

For batch ingestion, one failed video should not crash the entire batch.

---

# 53. Logging

Use Python logging.

Include:

```text
video ID
stage
timestamp
duration
candidate count
selected count
processing time
```

Avoid logging full transcripts or sensitive document contents.

---

# 54. Tests

Write unit tests for:

## Metadata

```text
duration extraction
audio detection
FPS detection
```

## Sampling

```text
10-second sampling
```

## Similarity

```text
near-duplicate frames
different frames
```

## Scene detection

Use mocked scene boundaries.

## OCR

Mock Tesseract.

## Frame selection

Test that:

- duplicates are removed
- temporal coverage works
- max frame count is respected
- high-scoring frames are selected

## Segmentation

Test:

```text
4-hour duration
```

without actually processing a 4-hour video.

## Transcript

Mock faster-whisper.

## Embedding

Mock Qwen models.

## Chroma

Use an isolated temporary ChromaDB.

---

# 55. Integration Test

Create a short test video fixture, e.g.:

```text
2–5 minutes
```

containing:

1. static screen
2. changed screen
3. different slide
4. talking-head section
5. text-heavy section

Verify:

```text
video
 ↓
metadata
 ↓
audio
 ↓
transcript
 ↓
candidate frames
 ↓
representative frames
 ↓
embeddings
 ↓
Chroma
 ↓
retrieval
```

---

# 56. Performance Test

Create a synthetic or fixture-based test representing:

```text
4 hours
```

without requiring a real 4-hour video.

Test that the algorithm scales approximately linearly with duration.

The system must not allocate memory proportional to the entire video size.

---

# 57. CLI

Implement:

```bash
python -m app.main ingest-video ./video.mp4
```

```bash
python -m app.main search-video "Where is B-tree indexing explained?"
```

```bash
python -m app.main benchmark-video ./video.mp4
```

```bash
python -m app.main video-status VIDEO_ID
```

---

# 58. Example End-to-End API

Expose:

```python
pipeline = VideoIngestionPipeline(
    video_processor=...,
    transcriber=...,
    frame_selector=...,
    text_embedder=...,
    vl_embedder=...,
    vector_store=...,
)

result = pipeline.ingest("lecture.mp4")
```

Return:

```python
class VideoIngestionResult:
    video_id: str
    duration_seconds: float
    transcript_segments: int
    candidate_frames: int
    representative_frames: int
    text_embeddings: int
    visual_embeddings: int
    elapsed_seconds: float
```

---

# 59. Important Resource Rule

Never do:

```python
frames = list(all_video_frames)
```

for a long video.

Never do:

```python
video_bytes = file.read()
```

for multi-gigabyte videos unless explicitly required.

Use streaming/incremental processing.

---

# 60. Important Cleanup Rule

Temporary files should be cleaned after successful completion.

Example:

```text
tmp/
    video_id/
        candidates/
        intermediate/
```

After:

```text
indexing complete
```

remove temporary files.

Keep:

```text
audio
selected frames
transcript
metadata/checkpoint
```

only if configured.

---

# 61. README Requirements

Update README with:

## Installation

macOS:

```bash
brew install ffmpeg
brew install tesseract
```

Python dependencies:

```bash
pip install ...
```

Document MPS usage for Apple Silicon.

Explain CPU fallback.

---

## Architecture

Include:

```text
Video
 ↓
FFmpeg
 ↓
Whisper + coarse frames
 ↓
Scene/visual/OCR filtering
 ↓
Representative frames
 ↓
Qwen embeddings
 ↓
ChromaDB
```

---

# 62. Explain Why This Works

Document that:

```text
Frame extraction is cheap.
VL embedding is expensive.
```

Therefore the optimization is:

```text
reduce frames before VL embedding
```

not:

```text
make the VL embedding process every frame faster
```

---

# 63. Important Multimodal RAG Principle

The transcript and visual frames complement each other.

Example:

```text
Query:
"What does the lecturer say about B-tree indexes?"
```

Text retrieval finds:

```text
01:02:10
"The B-tree index..."
```

Visual retrieval finds:

```text
01:02:25
[B-tree diagram]
```

Both should resolve to the same:

```text
VideoSegment
```

The LLM receives:

```text
Transcript
+
Representative frames
+
Timestamp
```

---

# 64. Do Not Over-Index

Avoid:

```text
one vector for every frame
```

Prefer:

```text
one text vector per meaningful transcript segment
+
one visual vector per representative frame
```

Optionally create a segment-level multimodal vector later.

---

# 65. Future Unified Multimodal Collection

Do not implement this as the default yet.

Keep the system extensible for:

```text
Qwen3-VL-Embedding
        ↓
unified multimodal collection
```

if later benchmarking shows that text and visual representations can be effectively searched together.

For now:

```text
text_embeddings
visual_embeddings
```

remain separate.

---

# 66. Deliverables

Implement actual working code for:

1. Long-video metadata extraction
2. Audio extraction
3. faster-whisper transcription
4. timestamped transcript segments
5. coarse frame sampling
6. PySceneDetect integration
7. visual similarity filtering
8. Tesseract OCR filtering
9. representative frame selection
10. Qwen3-Embedding
11. Qwen3-VL-Embedding
12. ChromaDB text collection
13. ChromaDB visual collection
14. video metadata
15. deterministic IDs
16. incremental indexing
17. checkpoint/resume
18. progress reporting
19. benchmark mode
20. CLI
21. unit tests
22. integration tests
23. README

---

# 67. Implementation Order

Do not implement everything at once.

Implement in this order:

## Phase 1

```text
Video
 ↓
FFprobe
 ↓
duration
```

Verify 3–4 hour videos are accepted.

---

## Phase 2

```text
Video
 ↓
FFmpeg
 ↓
audio
 ↓
faster-whisper
 ↓
timestamped transcript
```

---

## Phase 3

```text
Video
 ↓
coarse sampling
 ↓
candidate frames
```

---

## Phase 4

```text
candidate frames
 ↓
visual similarity
 ↓
deduplication
```

---

## Phase 5

```text
candidate frames
 ↓
PySceneDetect
 ↓
scene boundaries
```

---

## Phase 6

```text
candidate frames
 ↓
Tesseract
 ↓
OCR change
```

---

## Phase 7

```text
scene + similarity + OCR + temporal coverage
 ↓
representative frames
```

---

## Phase 8

```text
transcript
 ↓
Qwen3-Embedding
 ↓
Chroma text collection
```

---

## Phase 9

```text
representative frames
 ↓
Qwen3-VL-Embedding
 ↓
Chroma visual collection
```

---

## Phase 10

```text
text retrieval
+
visual retrieval
 ↓
merge
 ↓
VideoSegment results
```

---

## Phase 11

Add:

```text
checkpoint/resume
benchmark
CLI
tests
documentation
```

---

# 68. Acceptance Criteria

The implementation is complete only if all of the following are true:

### Long video

A 3–4 hour video is accepted and processed without being truncated.

### Memory

The entire video is never loaded into RAM.

### Sampling

The system does not extract/embed every frame.

### Reduction

The system reports:

```text
candidate frames
representative frames
reduction percentage
```

### Transcript

The complete video transcript has timestamps.

### Visual retrieval

Representative frames are embedded using Qwen3-VL-Embedding.

### Text retrieval

Transcript segments are embedded using Qwen3-Embedding.

### Storage

ChromaDB contains separate text and visual collections.

### Metadata

Every result contains:

```text
video_id
segment_id
timestamp
source
```

### Idempotency

Running the same video twice does not create duplicates.

### Resume

A failed long-video job can resume from a completed checkpoint.

### Testing

Unit and integration tests pass.

---

# 69. Final Target Architecture

The final implementation should look like:

```text
                                VIDEO
                                  |
                                  v
                              FFprobe
                                  |
                                  v
                          VideoMetadata
                                  |
                +-----------------+-----------------+
                |                                   |
                v                                   v
             FFmpeg                            FFmpeg/OpenCV
             Audio                              Coarse Frames
                |                                   |
                v                                   v
        faster-whisper                        Candidate Frames
                |                                   |
                v                         +---------+---------+
        Timestamped Transcript            |                   |
                |                         v                   v
                |                    PySceneDetect       Similarity
                |                         |                   |
                |                         +---------+---------+
                |                                   |
                |                                  OCR
                |                                   |
                +------------------+----------------+
                                   |
                                   v
                         Representative Selector
                                   |
                    +--------------+--------------+
                    |                             |
                    v                             v
              Transcript                     Selected Frames
                    |                             |
                    v                             v
          Qwen3-Embedding                Qwen3-VL-Embedding
                    |                             |
                    v                             v
             ChromaDB                        ChromaDB
          text_embeddings                 visual_embeddings
                    |                             |
                    +--------------+--------------+
                                   |
                                   v
                              Retriever
                                   |
                                   v
                               Reranker
                                   |
                                   v
                                  LLM
                                   |
                                   v
                                Answer
```

---

# 70. Final Engineering Instruction

Before implementing:

1. Inspect the existing repository.
2. Identify the current video-duration cutoff.
3. Identify current video libraries.
4. Identify current Docling/LangChain/Chroma abstractions.
5. Reuse existing abstractions where appropriate.
6. Show a concise implementation plan.
7. Implement Phase 1 first.
8. Run tests.
9. Continue phase by phase.
10. Do not invent APIs for Qwen models.
11. Verify the currently installed/model-supported API before implementation.
12. Keep all model names configurable.
13. Keep sampling parameters configurable.
14. Keep OCR optional.
15. Keep the pipeline resumable.
16. Measure the reduction in frames.
17. Never silently truncate a long video.
18. Never process all frames through the expensive VL embedding model.

The primary optimization target is:

```text
3–4 hour video
      ↓
cheap coarse sampling
      ↓
~1,000–2,000 candidates
      ↓
visual/scene/OCR filtering
      ↓
~100–500 meaningful frames
      ↓
Qwen3-VL-Embedding
```

while preserving:

```text
complete transcript
+
timestamps
+
representative visual content
+
retrieval metadata
```

The final system should optimize for **semantic coverage per expensive embedding**, not maximum frame count.
