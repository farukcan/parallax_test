"""Render a looping diagonal parallax video with DepthFlow.

Examples:
  python render_parallax.py test2.png
  python render_parallax.py test_image.jpg -o out.mp4
  python render_parallax.py photo.png --time 4 --model large
"""

import argparse
import math
from pathlib import Path

from attrs import define
from depthflow.estimators.anything import DepthAnythingV2
from depthflow.scene import DepthScene
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent

MODEL_MAP = {
    "small": DepthAnythingV2.Model.Small,
    "base": DepthAnythingV2.Model.Base,
    "large": DepthAnythingV2.Model.Large,
}


@define
class DiagonalParallax(DepthScene):
    """Looping diagonal parallax that starts/ends on the original photo."""

    height_peak: float = 0.06
    isometric_peak: float = 0.15
    offset_peak: float = 0.10

    def update(self):
        # cycle: 0 -> 2π over one loop. At 0 and 2π, wave=0 → exact original frame.
        s = math.sin(self.cycle)
        wave = 0.5 * (1.0 - math.cos(self.cycle))  # 0 at start/end, 1 at midpoint

        self.state.zoom = 1.0
        self.state.sticky = True
        self.state.steady = 0.28
        self.state.focus = 0.28
        self.state.height = self.height_peak * wave
        self.state.isometric = self.isometric_peak * wave
        self.state.offset = (self.offset_peak * s, -self.offset_peak * s)


def load_oriented_image(path: Path) -> Image.Image:
    """Load image and apply EXIF orientation."""
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a looping diagonal parallax video from an image.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input image path (jpg/png/webp/...)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output video path (default: <input_stem>_parallax.mp4)",
    )
    parser.add_argument(
        "-t", "--time",
        type=float,
        default=4.0,
        help="Loop duration in seconds (default: 4)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Output frames per second (default: 30)",
    )
    parser.add_argument(
        "--model",
        choices=sorted(MODEL_MAP),
        default="large",
        help="DepthAnythingV2 model size (default: large)",
    )
    parser.add_argument(
        "--max-side",
        type=int,
        default=1920,
        help="Longest output side in pixels (default: 1920)",
    )
    parser.add_argument(
        "--ssaa",
        type=float,
        default=2.0,
        help="Supersampling anti-aliasing factor (default: 2)",
    )
    parser.add_argument(
        "--height",
        type=float,
        default=0.06,
        help="Peak parallax height / zoom-like strength (default: 0.06)",
    )
    parser.add_argument(
        "--isometric",
        type=float,
        default=0.15,
        help="Peak isometric strength (default: 0.15)",
    )
    parser.add_argument(
        "--offset",
        type=float,
        default=0.10,
        help="Peak diagonal camera offset (default: 0.10)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"Input not found: {input_path}")

    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else input_path.with_name(f"{input_path.stem}_parallax.mp4")
    )

    image = load_oriented_image(input_path)
    src_w, src_h = image.size
    scale = args.max_side / max(src_w, src_h)
    out_w = max(2, int(src_w * scale) // 2 * 2)
    out_h = max(2, int(src_h * scale) // 2 * 2)

    scene = DiagonalParallax(
        backend="headless",
        height_peak=args.height,
        isometric_peak=args.isometric,
        offset_peak=args.offset,
    )
    scene.estimator = DepthAnythingV2(
        model=MODEL_MAP[args.model],
        sigma=0.6,
        thicken=5,
        post=True,
    )
    scene.ffmpeg.h264(preset="medium")
    scene.input(image=image)
    scene.main(
        output=output_path,
        time=args.time,
        fps=args.fps,
        ssaa=args.ssaa,
        width=out_w,
        height=out_h,
        turbo=False,
    )
    print(f"Saved: {output_path} ({src_w}x{src_h} → {out_w}x{out_h})")


if __name__ == "__main__":
    main()
