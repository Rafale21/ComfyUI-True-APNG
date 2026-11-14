"""Standalone APNG check: python check_apng.py animation.apng"""

import argparse
import json

from apng_encoder import verify_apng


def main():
    parser = argparse.ArgumentParser(description="Vérifie et décode un APNG exporté par True APNG.")
    parser.add_argument("file", help="Chemin du fichier .apng à vérifier")
    options = parser.parse_args()
    try:
        result = verify_apng(options.file)
    except (OSError, ValueError, SyntaxError, EOFError) as exc:
        parser.exit(1, f"APNG invalide : {exc}\n")
    print(json.dumps({
        "valid": True,
        "frames": result["frames"],
        "width": result["size"][0],
        "height": result["size"][1],
        "fps": float(result["fps"]),
        "duration_seconds": float(result["duration"]),
        "loop": result["loop"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
