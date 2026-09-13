# mux a wav onto an existing mp4 (video stream-copied, audio encoded to aac).
# for AE/AME renders that arrive silent: uv run python scripts/mux_sound.py video.mp4 bed.wav out.mp4
import sys
from pathlib import Path

import av

AUDIO_RATE = 44100


def mux(video_path: Path, wav_path: Path, out_path: Path) -> None:
    src = av.open(str(video_path))
    snd = av.open(str(wav_path))
    dst = av.open(str(out_path), "w")

    in_v = src.streams.video[0]
    out_v = dst.add_stream_from_template(in_v)
    out_a = dst.add_stream("aac", rate=AUDIO_RATE)
    resampler = av.AudioResampler(format="fltp", layout="stereo", rate=AUDIO_RATE)

    for packet in src.demux(in_v):
        if packet.dts is None:
            continue
        packet.stream = out_v
        dst.mux(packet)

    for frame in snd.decode(audio=0):
        for out_frame in resampler.resample(frame):
            for packet in out_a.encode(out_frame):
                dst.mux(packet)
    for packet in out_a.encode():
        dst.mux(packet)

    dst.close()
    snd.close()
    src.close()


if __name__ == "__main__":
    video, wav, out = (Path(p) for p in sys.argv[1:4])
    mux(video, wav, out)
    print(f"wrote {out}")
