import os
import json
import numpy as np
import faiss

from embedding_client import EmbeddingClient

class SearchService:
    """
    Handles loading the vector index and performing searches.
    """
    def __init__(self):
        self.embedding_client = EmbeddingClient()

        home_dir = os.path.expanduser("~")
        self.index_path = os.path.join(home_dir, ".labscribe_index.faiss")
        self.metadata_path = os.path.join(home_dir, ".labscribe_index_meta.json")

        self.index = None
        self.metadata = []
        self.is_ready = self._load_index()

    def _load_index(self):
        """
        Loads the FAISS index and metadata from disk.
        Returns True if successful, False otherwise.
        """
        print("Loading search index...")
        if not os.path.exists(self.index_path) or not os.path.exists(self.metadata_path):
            print("Warning: Index files not found. Please build the index first.")
            return False

        try:
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)

            print(f"Search index loaded successfully. Index contains {self.index.ntotal} vectors.")
            return True
        except Exception as e:
            print(f"Error loading search index: {e}")
            return False

    def search(self, query_text, k=5):
        """
        Performs a similarity search for the given query text.

        Args:
            query_text (str): The user's search query.
            k (int): The number of top results to return.

        Returns:
            list[dict]: A list of result dictionaries, each containing
                        the source note info and the relevant text chunk.
                        Returns an empty list if not ready or on error.
        """
        if not self.is_ready:
            print("Search service is not ready. Index is not loaded.")
            return []

        if not query_text:
            return []

        print(f"Performing search for: '{query_text}'")
        query_embedding = self.embedding_client.generate_embedding(query_text)

        if query_embedding is None:
            print("Error: Failed to generate embedding for the query.")
            return []

        # FAISS expects a 2D array of shape (n_queries, embedding_dim)
        query_embedding_np = np.array([query_embedding]).astype('float32')

        try:
            distances, indices = self.index.search(query_embedding_np, k)

            results = []
            # indices is a 2D array, e.g., [[idx1, idx2, ...]]
            for i, idx in enumerate(indices[0]):
                if idx != -1: # FAISS returns -1 for no result
                    result_item = self.metadata[idx]
                    result_item['distance'] = float(distances[0][i])
                    results.append(result_item)

            print(f"Search found {len(results)} results.")
            return results

        except Exception as e:
            print(f"An error occurred during FAISS search: {e}")
            return []

if __name__ == '__main__':
    # To run this standalone for testing:
    # 1. Make sure you have run indexing_service.py to create the index files.
    # 2. Make sure your Ollama server is running.
    searcher = SearchService()
    if searcher.is_ready:
        # Replace with a query relevant to your notes
        test_query = "What is the status of Project A?"
        search_results = searcher.search(test_query, k=3)

        if search_results:
            print("\n--- Search Results ---")
            for res in search_results:
                print(f"Source: {res['source_note_title']} (Distance: {res['distance']:.2f})")
                print(f"Text: \"...{res['chunk_text']}...\"")
                print("-" * 20)
        else:
            print("No results found.")
