from src.voice.audio.sentence import SentenceChunker


def test_splits_on_sentence_boundaries_once_followed_by_more_text():
    chunker = SentenceChunker(min_chars=1)
    # A boundary is only known to be a boundary when more text follows it.
    assert chunker.feed("Hello there. How are ") == ["Hello there."]
    assert chunker.feed("you?") == []
    assert chunker.flush() == "How are you?"


def test_waits_for_minimum_length():
    chunker = SentenceChunker(min_chars=20)
    assert chunker.feed("Hi. ") == []
    chunks = chunker.feed("This is a much longer sentence. And more text follows here ")
    assert chunks
    assert chunks[0] == "Hi. This is a much longer sentence."


def test_caps_runaway_buffer_without_punctuation():
    chunker = SentenceChunker(min_chars=10, max_chars=30)
    chunks = chunker.feed("word " * 20)
    assert chunks
    assert all(len(chunk) <= 30 for chunk in chunks)


def test_does_not_split_common_abbreviations():
    chunker = SentenceChunker(min_chars=1)
    chunks = chunker.feed("Use e.g. the sample. Then continue. ")
    assert chunks[0] == "Use e.g. the sample."


def test_flush_returns_trailing_text():
    chunker = SentenceChunker(min_chars=5)
    chunker.feed("partial thought")
    assert chunker.flush() == "partial thought"
    assert chunker.flush() is None
