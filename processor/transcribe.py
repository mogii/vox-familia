"""Local speech-to-text with faster-whisper, returning word-level timings.

faster-whisper decodes the audio track straight out of the video file, so
there's no separate audio-extraction step.
"""

import config


def transcribe(video_path):
    """Return (words, full_text).

    words: list of {"text", "start", "end"} in seconds, in spoken order.
    """
    from faster_whisper import WhisperModel

    device = config.WHISPER_DEVICE
    compute_type = config.WHISPER_COMPUTE_TYPE
    if device == "auto":
        device = "cpu"
        compute_type = compute_type or "int8"
    compute_type = compute_type or ("float16" if device == "cuda" else "int8")

    print(f"[asr] 加载 Whisper 模型 {config.WHISPER_MODEL} ({device}/{compute_type}) ...")
    model = WhisperModel(config.WHISPER_MODEL, device=device, compute_type=compute_type)

    print("[asr] 转写中（首次会下载模型，请耐心等）...")
    segments, info = model.transcribe(
        video_path,
        language=config.WHISPER_LANGUAGE,
        word_timestamps=True,
        vad_filter=True,
    )

    words = []
    full = []
    for seg in segments:
        full.append(seg.text)
        if seg.words:
            for w in seg.words:
                words.append(
                    {"text": w.word, "start": float(w.start), "end": float(w.end)}
                )
        else:
            # Fallback if word timings are missing for a segment.
            words.append(
                {"text": seg.text, "start": float(seg.start), "end": float(seg.end)}
            )

    return words, "".join(full).strip()
