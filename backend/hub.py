import os


def configure_hub():
    # Windows standard-user installs must not require symlink privileges.
    # HF 0.30 can race its per-directory probe when downloading concurrently.
    if os.name == "nt":
        from huggingface_hub import file_download
        file_download.are_symlinks_supported = lambda cache_dir=None: False
