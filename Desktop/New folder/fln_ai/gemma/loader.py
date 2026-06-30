import os
import sys
import time
import subprocess
import logging
from typing import Optional

from fln_ai.config import (
    GEMMA_REPO_ID, GEMMA_FILENAME, GEMMA_MMPROJ,
    GEMMA_CACHE_DIR, GEMMA_N_CTX, GEMMA_N_GPU_LAYERS,
    GEMMA_TEMPERATURE, GEMMA_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


class GemmaLoader:
    """Gemma Vision Intelligence — model loading and lifecycle management.

    Loads Gemma 4 26B A4B GGUF with llama-cpp-python across multiple GPUs.
    """

    def __init__(self):
        self.llm = None
        self.chat_handler = None
        self.loaded = False

    def load(self, force_reinstall: bool = False):
        """Load the Gemma model. Installs llama-cpp-python if needed."""
        if self.loaded and self.llm is not None:
            logger.info("Gemma model already loaded.")
            return

        self._ensure_deps(force_reinstall)
        self._load_model()
        self.loaded = True

    def _ensure_deps(self, force_reinstall: bool):
        import torch
        torch_ver = torch.version.cuda or ""
        wheel_map = {
            "12.1": "cu121", "12.2": "cu122", "12.3": "cu123",
            "12.4": "cu124", "12.5": "cu125", "12.6": "cu126",
        }
        cuda_wheel = wheel_map.get(torch_ver, "cu124")
        logger.info("CUDA %s → using %s wheel", torch_ver, cuda_wheel)

        if force_reinstall:
            logger.info("Installing llama-cpp-python with %s wheel...", cuda_wheel)
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "llama-cpp-python",
                f"--extra-index-url",
                f"https://abetlen.github.io/llama-cpp-python/whl/{cuda_wheel}",
                "--force-reinstall", "--no-cache-dir", "-q",
            ])

    def _load_model(self):
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Gemma4ChatHandler

        os.makedirs(GEMMA_CACHE_DIR, exist_ok=True)

        logger.info("Loading mmproj...")
        self.chat_handler = Gemma4ChatHandler.from_pretrained(
            repo_id=GEMMA_REPO_ID,
            filename=GEMMA_MMPROJ,
            local_dir=GEMMA_CACHE_DIR,
            verbose=False,
        )
        logger.info("Chat handler loaded.")

        logger.info("Loading Gemma 4 26B A4B (this may take a few minutes)...")
        start = time.time()
        self.llm = Llama.from_pretrained(
            repo_id=GEMMA_REPO_ID,
            filename=GEMMA_FILENAME,
            local_dir=GEMMA_CACHE_DIR,
            chat_handler=self.chat_handler,
            n_gpu_layers=GEMMA_N_GPU_LAYERS,
            n_ctx=GEMMA_N_CTX,
            flash_attn=True,
            verbose=False,
        )
        elapsed = (time.time() - start) / 60
        logger.info("Model loaded in %.1f min", elapsed)

    @property
    def model(self):
        if not self.loaded:
            self.load()
        return self.llm

    def unload(self):
        """Free GPU memory."""
        self.llm = None
        self.chat_handler = None
        self.loaded = False
        import gc
        gc.collect()
        import torch
        torch.cuda.empty_cache()
        logger.info("Model unloaded, GPU memory freed.")
