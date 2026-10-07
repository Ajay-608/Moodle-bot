import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moodlebot.settings")
django.setup()

from core.faiss_index import build_faiss_index, document_ids, index_path


def main():
    current_ids = document_ids()
    if not current_ids:
        raise RuntimeError(
            "No Documents found. Run 'python manage.py initialize_knowledge_base' "
            "before building FAISS."
        )

    index = build_faiss_index()
    print(
        f"Built FAISS index with {index.ntotal} vectors for "
        f"{len(current_ids)} Documents at {index_path()}."
    )


if __name__ == "__main__":
    main()
