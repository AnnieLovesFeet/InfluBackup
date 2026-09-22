"""Build influencer image galleries from the influencers directory.

By default the script converts, deduplicates, renames images, and updates only
the JSON ``images`` keys. Use --preview to print the plan without changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
PROFILE_NAMES = {"profile", "profile-image", "profile_image"}
HASH_SIZE = 32
AHASH_SIZE = 16
AHASH_DISTANCE_LIMIT = 4


@dataclass
class ImageCandidate:
	source: Path
	exact_hash: str
	average_hash: int
	aspect_ratio: float


def parse_arguments() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--preview",
		action="store_true",
		help="print the plan without changing files",
	)
	parser.add_argument(
		"--json",
		type=Path,
		default=None,
		help="path to influencers.json (defaults to the project file)",
	)
	parser.add_argument(
		"--root",
		type=Path,
		default=None,
		help="path to the influencers directory (defaults to the project folder)",
	)
	return parser.parse_args()


def project_paths(json_path: Path | None, influencers_root: Path | None) -> tuple[Path, Path]:
	project_root = Path(__file__).resolve().parents[1]
	return (
		(json_path or project_root / "influencers.json").resolve(),
		(influencers_root or project_root / "influencers").resolve(),
	)


def is_gallery_image(path: Path) -> bool:
	return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def is_profile_image(path: Path) -> bool:
	return path.stem.lower() in PROFILE_NAMES


def average_hash(image: Image.Image) -> int:
	grayscale = image.convert("L").resize((AHASH_SIZE, AHASH_SIZE), Image.Resampling.LANCZOS)
	pixels = list(grayscale.get_flattened_data())
	average = sum(pixels) / len(pixels)
	return sum(1 << index for index, pixel in enumerate(pixels) if pixel >= average)


def image_candidate(path: Path) -> ImageCandidate:
	with Image.open(path) as source_image:
		image = ImageOps.exif_transpose(source_image).convert("RGB")
		normalized = image.resize((HASH_SIZE, HASH_SIZE), Image.Resampling.LANCZOS)
		exact_hash = hashlib.sha256(normalized.tobytes()).hexdigest()
		return ImageCandidate(
			source=path,
			exact_hash=exact_hash,
			average_hash=average_hash(image),
			aspect_ratio=image.width / image.height,
		)


def is_duplicate(candidate: ImageCandidate, accepted: list[ImageCandidate]) -> bool:
	for previous in accepted:
		if candidate.exact_hash == previous.exact_hash:
			return True

		ratio_difference = abs(candidate.aspect_ratio - previous.aspect_ratio)
		hash_difference = (candidate.average_hash ^ previous.average_hash).bit_count()
		if ratio_difference <= 0.03 and hash_difference <= AHASH_DISTANCE_LIMIT:
			return True

	return False


def collect_candidates(folder: Path) -> tuple[list[ImageCandidate], list[Path]]:
	candidates: list[ImageCandidate] = []
	duplicates: list[Path] = []

	for path in sorted(folder.rglob("*")):
		if not is_gallery_image(path) or is_profile_image(path):
			continue

		try:
			candidate = image_candidate(path)
		except (OSError, SyntaxError) as error:
			print(f"  POMINIĘTO uszkodzony obraz {path}: {error}", file=sys.stderr)
			continue

		if is_duplicate(candidate, candidates):
			duplicates.append(path)
		else:
			candidates.append(candidate)

	return candidates, duplicates


def convert_to_jpg(source: Path, target: Path) -> None:
	target.parent.mkdir(parents=True, exist_ok=True)
	with Image.open(source) as source_image:
		image = ImageOps.exif_transpose(source_image).convert("RGB")
		image.save(target, "JPEG", quality=95, optimize=True)


def relative_json_path(path: Path, project_root: Path) -> str:
	return path.relative_to(project_root).as_posix()


def process_folder(
	folder: Path,
	project_root: Path,
	apply_changes: bool,
) -> tuple[list[str], int, int]:
	code = folder.name
	candidates, duplicates = collect_candidates(folder)
	image_paths: list[str] = []
	temporary_folder = folder / ".parser-tmp"

	print(f"{folder.relative_to(project_root)}: {len(candidates)} zdjęć, {len(duplicates)} duplikatów")

	if not apply_changes:
		image_paths = [
			relative_json_path(folder / f"{code}-{index:06d}.jpg", project_root)
			for index in range(1, len(candidates) + 1)
		]
		return image_paths, len(duplicates), len(candidates)

	try:
		temporary_folder.mkdir(exist_ok=True)
		staged_paths: list[Path] = []

		for index, candidate in enumerate(candidates, start=1):
			staged_path = temporary_folder / f"{code}-{index:06d}.jpg"
			convert_to_jpg(candidate.source, staged_path)
			staged_paths.append(staged_path)

		for candidate in candidates:
			if candidate.source.exists():
				candidate.source.unlink()
		for duplicate in duplicates:
			if duplicate.exists():
				duplicate.unlink()

		for staged_path in staged_paths:
			target = folder / staged_path.name
			if target.exists():
				target.unlink()
			staged_path.replace(target)
			image_paths.append(relative_json_path(target, project_root))
	finally:
		if temporary_folder.exists():
			shutil.rmtree(temporary_folder)

	return image_paths, len(duplicates), len(candidates)


def load_json(json_path: Path) -> list[dict[str, Any]]:
	with json_path.open("r", encoding="utf-8-sig") as file:
		data = json.load(file)

	if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
		raise ValueError("influencers.json musi zawierać tablicę obiektów.")
	return data


def update_images(
	data: list[dict[str, Any]],
	processed: dict[tuple[str, str], list[str]],
) -> int:
	updated = 0
	for influencer in data:
		key = (str(influencer.get("group", "")), str(influencer.get("code", "")))
		if key in processed and influencer.get("images") != processed[key]:
			influencer["images"] = processed[key]
			updated += 1
	return updated


def main() -> int:
	args = parse_arguments()
	json_path, influencers_root = project_paths(args.json, args.root)
	project_root = json_path.parent

	if not json_path.exists():
		print(f"Brak pliku JSON: {json_path}", file=sys.stderr)
		return 1
	if not influencers_root.is_dir():
		print(f"Brak katalogu influencerek: {influencers_root}", file=sys.stderr)
		return 1

	data = load_json(json_path)
	processed: dict[tuple[str, str], list[str]] = {}
	for group_folder in sorted(path for path in influencers_root.iterdir() if path.is_dir()):
		for influencer_folder in sorted(path for path in group_folder.iterdir() if path.is_dir()):
			image_paths, _, _ = process_folder(influencer_folder, project_root, not args.preview)
			processed[(group_folder.name, influencer_folder.name)] = image_paths

	if not args.preview:
		updated = update_images(data, processed)
		with json_path.open("w", encoding="utf-8", newline="\n") as file:
			json.dump(data, file, ensure_ascii=False, indent=4)
			file.write("\n")
		print(f"Zapisano {updated} pól images w {json_path.name}.")
	else:
		print("TRYB PODGLĄDU: żadne pliki nie zostały zmienione.")

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
