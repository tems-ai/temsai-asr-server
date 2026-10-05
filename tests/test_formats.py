from asr_server.formats import to_srt, to_vtt

RESULT = {
    "segments": [
        {"start": 0.0, "end": 1.25, "text": " hello "},
        {"start": 3661.5, "end": 3662.0, "text": "world"},
    ]
}


def test_srt():
    assert to_srt(RESULT) == ("1\n00:00:00,000 --> 00:00:01,250\nhello\n\n2\n01:01:01,500 --> 01:01:02,000\nworld\n")


def test_vtt():
    assert to_vtt(RESULT) == (
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.250\nhello\n\n01:01:01.500 --> 01:01:02.000\nworld\n"
    )


def test_empty_and_missing_segments():
    for result in ({}, {"segments": []}, {"segments": None}):
        assert to_srt(result) == ""
        assert to_vtt(result) == "WEBVTT\n\n"


def test_blank_text_segments_are_skipped_and_numbering_stays_dense():
    result = {
        "segments": [
            {"start": 0, "end": 1, "text": "  "},
            {"start": 1, "end": 2, "text": None},
            {"start": 2, "end": 3, "text": "x"},
        ]
    }
    assert to_srt(result) == "1\n00:00:02,000 --> 00:00:03,000\nx\n"


def test_negative_and_string_times_are_clamped_and_coerced():
    result = {"segments": [{"start": -0.4, "end": "1.5", "text": "x"}]}
    assert "00:00:00,000 --> 00:00:01,500" in to_srt(result)


def test_long_text_is_not_truncated():
    text = "word " * 5000
    assert text.strip() in to_srt({"segments": [{"start": 0, "end": 1, "text": text}]})
