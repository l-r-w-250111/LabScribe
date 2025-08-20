import os
import json
import numpy as np
import faiss

import config
from embedding_client import EmbeddingClient
from settings import Settings

class IndexingService:
    """
    Handles the creation and management of the searchable vector index for notes.
    """
    def __init__(self):
        self.settings = Settings()
        self.embedding_client = EmbeddingClient()
        
        # Define paths for the index and its metadata in the user's home directory
        home_dir = os.path.expanduser("~")
        self.index_path = os.path.join(home_dir, ".labscribe_index.faiss")
        self.metadata_path = os.path.join(home_dir, ".labscribe_index_meta.json")

    def _extract_text_from_note(self, note_data):
        """Extracts all relevant text from a note's modules."""
        full_text = []
        
        # Add note title
        if 'title' in note_data:
            full_text.append(note_data['title'])

        for module in note_data.get("modules", []):
            content = module.get("content")
            if isinstance(content, str):
                full_text.append(content)
            elif isinstance(content, dict):
                # For dicts, concatenate all string values
                for key, value in content.items():
                    if isinstance(value, str):
                        full_text.append(f"{key}: {value}")
        
        return "\n".join(full_text)

    def _chunk_text(self, text):
        """Splits text into smaller, overlapping chunks using settings from config."""
        if not text:
            return []
        
        chunk_size = config.RAG_CHUNK_SIZE
        overlap = config.RAG_CHUNK_OVERLAP

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def build_index(self):
        """
        Scans all notes, generates embeddings, and builds a FAISS index.
        This is a long-running process.
        """
        print("Starting to build search index...")
        save_folder = self.settings.get('save_folder')
        if not os.path.isdir(save_folder):
            print(f"Error: Save folder '{save_folder}' not found.")
            return False

        all_chunks_metadata = []
        all_embeddings = []
        
        note_files = [f for f in os.listdir(save_folder) if f.endswith(".json") and not f.endswith(".project.json")]
        total_files = len(note_files)

        for i, filename in enumerate(note_files):
            print(f"Processing file {i+1}/{total_files}: {filename}")
            file_path = os.path.join(save_folder, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    note_data = json.load(f)
                
                text_content = self._extract_text_from_note(note_data)
                chunks = self._chunk_text(text_content)
                
                for chunk in chunks:
                    embedding = self.embedding_client.generate_embedding(chunk)
                    if embedding:
                        all_embeddings.append(embedding)
                        # Store metadata to link embedding back to source
                        all_chunks_metadata.append({
                            "source_note_path": file_path,
                            "source_note_title": note_data.get('title', 'Untitled'),
                            "chunk_text": chunk
                        })

            except (IOError, json.JSONDecodeError) as e:
                print(f"Warning: Could not process file {filename}: {e}")
                continue
        
        if not all_embeddings:
            print("No text found in any notes. Index not built.")
            return False

        print(f"Generated {len(all_embeddings)} embeddings. Building FAISS index...")
        
        # --- Build and Save FAISS Index ---
        embedding_dim = len(all_embeddings[0])
        embeddings_array = np.array(all_embeddings).astype('float32')
        
        index = faiss.IndexFlatL2(embedding_dim)
        index.add(embeddings_array)
        
        faiss.write_index(index, self.index_path)
        print(f"FAISS index saved to {self.index_path}")

        # --- Save Metadata ---
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(all_chunks_metadata, f, indent=4)
        print(f"Index metadata saved to {self.metadata_path}")
        
        print("Search index build complete.")
        return True

if __name__ == '__main__':
    # To run this standalone for testing:
    # 1. Make sure you have some notes in your ELN_Notes folder.
    # 2. Make sure your Ollama server is running with the embedding model.
    service = IndexingService()
    service.build_index()
