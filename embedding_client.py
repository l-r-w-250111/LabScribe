import requests
import json
import config

class EmbeddingClient:
    """
    A client to communicate with an Ollama server to generate text embeddings.
    """
    def __init__(self, api_url=config.OLLAMA_API_URL, model=config.EMBEDDING_MODEL):
        """
        Initializes the EmbeddingClient.

        Args:
            api_url (str): The base URL of the Ollama API.
            model (str): The name of the embedding model to use.
        """
        self.api_url = api_url.rstrip('/') + "/api/embeddings"
        self.model = model
        self.session = requests.Session()

    def generate_embedding(self, text):
        """
        Generates an embedding for the given text using the Ollama API.

        Args:
            text (str): The text to embed.

        Returns:
            list[float] | None: A list of floats representing the embedding,
                                or None if an error occurs.
        """
        if not text:
            return None

        payload = {
            "model": self.model,
            "prompt": text
        }

        try:
            response = self.session.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            
            response_json = response.json()
            return response_json.get("embedding")

        except requests.exceptions.RequestException as e:
            print(f"Error communicating with Ollama API at {self.api_url}: {e}")
            return None
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON response from Ollama API. Response text: {response.text}")
            return None

if __name__ == '__main__':
    # Example usage and testing
    # This assumes the Ollama server is running and has the specified model.
    client = EmbeddingClient()
    
    # Check if the model is available on the server
    try:
        res = requests.get(config.OLLAMA_API_URL.rstrip('/') + "/api/tags")
        if res.status_code == 200:
            models = [m['name'] for m in res.json().get('models', [])]
            print("Available models:", models)
            if config.EMBEDDING_MODEL not in models:
                 print(f"\n--- WARNING ---")
                 print(f"The specified embedding model '{config.EMBEDDING_MODEL}' is not available in Ollama.")
                 print(f"Please make sure you have run 'ollama pull {config.EMBEDDING_MODEL}'")
                 print(f"-----------------\n")

    except requests.exceptions.RequestException as e:
        print(f"Could not connect to Ollama server at {config.OLLAMA_API_URL} to check for models. {e}")


    test_text = "This is a test sentence for generating an embedding."
    print(f"Generating embedding for: '{test_text}'")
    embedding = client.generate_embedding(test_text)

    if embedding:
        print(f"Successfully generated embedding of dimension: {len(embedding)}")
        print(f"First 5 dimensions: {embedding[:5]}")
    else:
        print("Failed to generate embedding.")
