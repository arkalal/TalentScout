"""Build (or rebuild) the FAISS resume index in vector_store/.

    python scripts/build_index.py [--force]
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talentscout.rag import ResumeIndex  # noqa: E402

if __name__ == "__main__":
    t = time.time()
    idx = ResumeIndex().load_or_build(force="--force" in sys.argv)
    print(f"Indexed {len(idx.chunks)} chunks from {len({c['candidate_id'] for c in idx.chunks})} resumes "
          f"in {time.time() - t:.1f}s -> vector_store/")
