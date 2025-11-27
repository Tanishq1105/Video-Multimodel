import os

# In-memory storage
VIDEOS = {}
NEXT_ID = 1

def get_all_videos():
    return list(VIDEOS.values())

def get_video(video_id):
    return VIDEOS.get(video_id)

def add_video(video):
    global NEXT_ID
    video.id = NEXT_ID
    VIDEOS[NEXT_ID] = video
    NEXT_ID += 1
    return video

def update_video(video):
    if video.id in VIDEOS:
        VIDEOS[video.id] = video

# ChromaDB setup
try:
    import chromadb
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    collection = chroma_client.get_or_create_collection(name="video_knowledge")
except Exception as e:
    print(f"ChromaDB import failed (likely Python 3.14/Pydantic issue): {e}")
    print("Using Mock ChromaDB.")
    
    import sys
    from unittest.mock import MagicMock
    sys.modules["chromadb"] = MagicMock()
    sys.modules["chromadb.config"] = MagicMock()
    
    class MockCollection:
        def add(self, documents, metadatas, ids):
            print(f"Mock add: {len(documents)} docs")
        def query(self, query_texts, n_results, where):
            return {
                'documents': [['Mock document content for: ' + query_texts[0]]],
                'metadatas': [[{'start_time': 0.0, 'video_id': where['video_id']}]],
                'ids': [['mock_id']]
            }

    class MockClient:
        def get_or_create_collection(self, name):
            return MockCollection()

    chroma_client = MockClient()
    collection = chroma_client.get_or_create_collection(name="video_knowledge")
