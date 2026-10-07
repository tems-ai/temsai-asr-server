# Accessibility

temsai-asr-server has no user interface. It is an HTTP API that turns speech
into text, so accessibility here means two things: the transcripts and
captions it produces, and this project's documentation. This file says what
works today, where the limits are, and how to tell us about a barrier.

## What the server provides

- **Transcripts and captions.** `response_format=text` returns a plain
  transcript; `srt` and `vtt` return timed captions that video players and
  browsers (WebVTT) can show. `verbose_json` adds per-word timestamps, which a
  client can use to build its own captions or highlight words as they are
  spoken.
- **Per-word confidence.** `verbose_json` gives each word a confidence in
  [0, 1] (see [Confidence semantics](README.md#confidence-semantics)). A client
  can use it to mark uncertain words, so a reviewer checks those first.
- **25 European languages**, detected automatically, with punctuation and
  capitalization in the output.
- **Self-hosted.** Audio never leaves your infrastructure, so recordings that
  are private or sensitive can still be transcribed.

## Known limitations

- **Captions need human review.** Speech recognition makes mistakes. Do not
  publish machine captions as the only accessible version of a recording
  without checking them: under WCAG 2.2 (success criteria 1.2.2 and 1.2.4),
  captions must be accurate. Low-confidence words show where to look first.
- **Cue length is not limited.** Each caption cue is one segment from the
  model, with no line wrapping and no limit on characters or duration. A cue
  can be 10 seconds or longer, more than caption style guides usually allow.
  To meet a style guide, build cues from `verbose_json` word timestamps in
  your client.
- **Speech only.** The output has no speaker labels and no descriptions of
  non-speech sounds such as `[alarm]` or `[music]`. Captions for deaf and
  hard-of-hearing viewers often need both; add them in review.
- **Files only, not live.** The server transcribes a complete upload. It does
  not stream, so it cannot produce live captions.
- **Accuracy varies by speaker.** Like other speech recognition models,
  Parakeet is likely to be less accurate for speech it saw little of in
  training, for example strong accents, speech impairments or children's
  speech. We have not measured this. Test with your own speakers before you
  rely on it.
- **Languages.** Only the [25 languages listed in the README](README.md#supported-languages) are recognized.
  Sign languages are out of scope for a speech model.

## Documentation

The documentation is Markdown on GitHub, so it works with screen readers,
browser zoom and GitHub's light, dark and high-contrast themes. We write
tables with header rows, give links descriptive text, and keep information in
text rather than only in images or color. If something in the documentation is
hard to use with your setup, that is a bug: please report it.

## Report a barrier

- Open an [issue](https://github.com/tems-ai/temsai-asr-server/issues/new/choose)
  and say in the title that it is about accessibility. Tell us what you were
  trying to do, what got in the way, and the assistive technology you use if
  it matters.
- If you prefer not to report in public, email **support@tems.ai** with
  "ACCESSIBILITY" in the subject.

Pull requests that improve accessibility are welcome; see
[CONTRIBUTING.md](CONTRIBUTING.md).

Last reviewed: 2026-10-07.
