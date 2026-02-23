import argparse
import os
from pathlib import Path


def resolve_repo_id(model_name: str) -> str:
    return model_name if "/" in model_name else f"sentence-transformers/{model_name}"


def main():
    parser = argparse.ArgumentParser(description="Download local rerank model for packaging")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Sentence-Transformers model name")
    parser.add_argument(
        "--output-root",
        default=str(Path(__file__).resolve().parents[1] / "app" / "resources" / "models" / "sentence-transformers"),
        help="Root directory to store downloaded model (absolute path or relative to project root)",
    )
    args = parser.parse_args()

    # Expand and normalize path
    output_root = Path(args.output_root).expanduser().resolve()

    repo_id = resolve_repo_id(args.model)
    model_leaf = args.model.split("/")[-1]
    target_dir = output_root / model_leaf
    os.makedirs(target_dir, exist_ok=True)

    print(f"[MODEL] Downloading {repo_id}")
    print(f"[MODEL] Target: {target_dir}")

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )

    print(f"[MODEL] Model stored at: {target_dir}")

    print("[MODEL] Download completed")


if __name__ == "__main__":
    main()
