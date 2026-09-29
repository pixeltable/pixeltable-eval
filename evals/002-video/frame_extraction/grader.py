"""
Grader for frame_extraction eval.

Frames come from a frame_iterator view, not a cv2 loop; captions and the
search index are computed columns / model indexes.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.Video", "declares a video column"),
    (r"frame_iterator", "extracts frames with frame_iterator"),
    (r"create_view|base\s*=|TableModel", "builds the frames view"),
    (r"chat_completions|image_url|vision|caption", "caption computed column via an LLM"),
    (r"add_embedding_index|__indexes__|EmbeddingIndex", "embedding index on captions"),
    (r"\.similarity\s*\(", "search over frames with .similarity()"),
]

NEGATIVE_PATTERNS = [
    (r"cv2\.VideoCapture|import cv2|imageio|ffmpeg", "manual frame extraction (use frame_iterator)"),
    (r"for\s+\w+\s+in\s+.*frames.*:\s*\n\s*.*(?:openai|chat_completions|client\.)",
     "imperative loop captioning frames"),
    (r"from pixeltable\.iterators\s+import|FrameIterator|VideoSplitter",
     "deprecated pixeltable.iterators shim (use pixeltable.functions.video)"),
    (r"from langchain", "imports LangChain"),
    (r"import chromadb|import pinecone|import faiss", "separate vector store"),
]
