"""Compare OCR engines on a pre-labeled local image manifest, without site requests."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import time


def prepare_numeric_captcha(image_bytes):
    """Normalize four colored digits of different sizes on a textured background."""
    from io import BytesIO

    import cv2
    import numpy as np
    from PIL import Image

    image = np.asarray(Image.open(BytesIO(image_bytes)).convert("RGB"))
    width = image.shape[1]
    output = Image.new("RGB", (160, 64), "white")
    for index in range(4):
        cell = image[:, index * width // 4:(index + 1) * width // 4]
        colors, counts = np.unique(cell.reshape(-1, 3), axis=0, return_counts=True)
        best = None
        best_score = 0
        for color_index in np.argsort(counts)[-16:]:
            color = colors[color_index]
            if counts[color_index] < 8:
                continue
            if int(color.max()) - int(color.min()) < 35 and color.mean() > 145:
                continue
            mask = np.all(cell == color, axis=2).astype("uint8")
            count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
            for component in range(1, count):
                x, y, w, h, area = stats[component]
                density = area / (w * h)
                if w < 3 or h < 5 or not .15 <= w / h <= 1.5 or density < .2:
                    continue
                score = area * density
                if score > best_score:
                    best_score = score
                    best = ((labels[y:y + h, x:x + w] == component) * 255).astype("uint8")
        if best is None:
            digit = Image.fromarray(cell)
        else:
            digit = Image.fromarray(255 - best).convert("RGB")
        scale = min(32 / digit.width, 48 / digit.height)
        digit = digit.resize((max(1, round(digit.width * scale)), max(1, round(digit.height * scale))), Image.Resampling.NEAREST)
        output.paste(digit, (index * 40 + (40 - digit.width) // 2, (64 - digit.height) // 2))
    stream = BytesIO()
    output.save(stream, "PNG")
    return stream.getvalue()


def decode_probability(result):
    if "text" in result:
        return result["text"]
    text = []
    previous = None
    for row in result["probability"]:
        char = result["charsets"][max(range(len(row)), key=row.__getitem__)]
        if char and char != previous:
            text.append(char)
        previous = char
    return "".join(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("ddddocr", "rapidocr"), default="ddddocr")
    parser.add_argument("--beta", action="store_true")
    parser.add_argument("--digits", action="store_true", help="Constrain South Plus to digits")
    parser.add_argument("--uncached", action="store_true")
    parser.add_argument("--preprocess-splus", action="store_true")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--ocr-version", choices=("v5", "v6"), default="v6")
    parser.add_argument("--language", default="ch")
    args = parser.parse_args()

    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "2"
    import onnxruntime as ort

    # This process-local wrapper caps every engine's ORT sessions equally.
    original_session = ort.InferenceSession

    def limited_session(*session_args, **kwargs):
        options = kwargs.get("sess_options") or ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        kwargs["sess_options"] = options
        return original_session(*session_args, **kwargs)

    ort.InferenceSession = limited_session
    manifest_bytes = args.samples.read_bytes()
    samples = json.loads(manifest_bytes)
    labels_hash = hashlib.sha256(manifest_bytes).hexdigest()
    hash_file = args.samples.with_name("labels.sha256")
    if hash_file.exists() and hash_file.read_text().strip() != labels_hash:
        raise ValueError("Labels changed after the dataset was frozen")

    from importlib.metadata import version

    engines = {}
    load_ms = 0
    predictions = []
    for sample in samples:
        image_path = args.samples.parent / sample["file"]
        data = image_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != sample["sha256"]:
            raise ValueError(f"Image changed: {sample['id']}")
        if args.preprocess_splus and sample["site"] == "splus":
            data = prepare_numeric_captcha(data)
        digits = args.digits and sample["site"] == "splus"
        key = digits if args.backend == "ddddocr" else False
        started = time.perf_counter()
        if key not in engines or args.uncached:
            if args.backend == "ddddocr":
                import ddddocr

                engine = ddddocr.DdddOcr(show_ad=False, beta=args.beta)
                if digits:
                    engine.set_ranges("0123456789")
            else:
                from rapidocr import EngineType, ModelType, OCRVersion, RapidOCR

                params = {
                    "Rec.engine_type": EngineType.ONNXRUNTIME,
                    "Rec.ocr_version": OCRVersion.PPOCRV6 if args.ocr_version == "v6" else OCRVersion.PPOCRV5,
                    "Rec.model_type": ModelType.TINY if args.ocr_version == "v6" else ModelType.MOBILE,
                    "Rec.lang_type": args.language,
                }
                if args.model_dir:
                    params["Global.model_root_dir"] = str(args.model_dir)
                engine = RapidOCR(params=params)
            engines[key] = engine
            load_ms += (time.perf_counter() - started) * 1000
        engine = engines[key]
        inference_started = time.perf_counter()
        if args.backend == "ddddocr":
            value = engine.classification(data, probability=digits)
            text = decode_probability(value) if isinstance(value, dict) else value
        else:
            result = engine(data, use_det=False, use_cls=False, use_rec=True)
            text = "".join(result.txts or ())
        label = sample.get("label")
        predictions.append({
            "id": sample["id"], "site": sample["site"], "label": label,
            "prediction": text, "exact_match": text == label if label is not None else None,
            "casefold_match": text.casefold() == label.casefold() if label is not None else None,
            "inference_ms": (time.perf_counter() - inference_started) * 1000,
            "total_ms": (time.perf_counter() - started) * 1000,
        })
        if args.uncached:
            engines.clear()

    summaries = {}
    for site in sorted({row["site"] for row in predictions}):
        rows = [row for row in predictions if row["site"] == site and row["label"] is not None]
        durations = sorted(row["inference_ms"] for row in rows)
        index = (len(durations) - 1) * .95
        lower = int(index)
        p95 = durations[lower] + (durations[min(lower + 1, len(durations) - 1)] - durations[lower]) * (index - lower)
        summaries[site] = {
            "labeled": len(rows), "exact_correct": sum(row["exact_match"] for row in rows),
            "casefold_correct": sum(row["casefold_match"] for row in rows),
            "median_ms": statistics.median(durations), "p95_ms": p95,
        }
    report = {
        "backend": args.backend, "version": version(args.backend), "onnxruntime": ort.__version__,
        "beta": args.beta, "digits": args.digits, "uncached": args.uncached,
        "preprocess_splus": args.preprocess_splus,
        "ocr_version": args.ocr_version if args.backend == "rapidocr" else None,
        "language": args.language if args.backend == "rapidocr" else None,
        "threads": {"intra_op": 2, "inter_op": 1}, "labels_sha256": labels_hash,
        "model_load_ms": load_ms, "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "summary": summaries, "predictions": predictions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != "predictions"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
