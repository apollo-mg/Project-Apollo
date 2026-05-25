import requests

def query_llm(prompt, temperature=0.7, max_tokens=2048):
    """
    Query a local LLM via Ollama API.
    
    Args:
        prompt (str): The user's prompt/question.
        temperature (float): Sampling temperature (0.0-1.0). Lower = more deterministic.
        max_tokens (int): Maximum tokens to generate in response.
        
    Returns:
        str: The LLM's generated response.
        
    Raises:
        requests.exceptions.RequestException: If connection fails or API returns error.
        ValueError: If parameters are invalid.
    """
    # Validate temperature range
    if not 0.0 <= temperature <= 1.0:
        raise ValueError(f"Temperature must be between 0.0 and 1.0, got {temperature}")
    
    # Validate max_tokens
    if max_tokens <= 0:
        raise ValueError(f"max_tokens must be positive, got {max_tokens}")
    
    # API endpoint configuration
    BASE_URL = "http://127.0.0.1:11434/api/chat"
    
    try:
        # Prepare the request payload
        payload = {
            "model": "llama2",  # Default model - can be overridden
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        # Make the API request
        response = requests.post(BASE_URL, json=payload)
        
        # Raise an exception for HTTP errors (4xx, 5xx)
        response.raise_for_status()
        
        # Parse and return the response
        result = response.json()
        
        if "message" in result:
            return result["message"]["content"]
        elif "response" in result:
            return result["response"]
        else:
            raise ValueError(f"Unexpected LLM response format: {result}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"\n⚠️  CONNECTION ERROR:")
        print(f"   Cannot connect to Ollama at {BASE_URL}")
        print(f"   Error: {e}")
        print(f"\n   Please ensure:")
        print(f"   1. Ollama service is running locally")
        print(f"   2. The model 'llama2' is downloaded and available")
        print(f"   3. Port 11434 is not blocked by firewall")
        raise
    except requests.exceptions.Timeout as e:
        print(f"\n⚠️  TIMEOUT ERROR:")
        print(f"   Request to Ollama timed out")
        print(f"   Error: {e}")
        raise
    except requests.exceptions.HTTPError as e:
        # Handle specific HTTP errors
        if response.status_code == 400:
            error_detail = response.json().get("error", "Bad Request")
            print(f"\n⚠️  BAD REQUEST (400):")
            print(f"   Error from Ollama: {error_detail}")
            print(f"   Check that the model 'llama2' exists and is loaded")
        elif response.status_code == 401:
            print(f"\n⚠️  UNAUTHORIZED (401):")
            print(f"   Ollama rejected the request")
        else:
            print(f"\n⚠️  HTTP ERROR ({response.status_code}):")
            print(f"   Error from Ollama: {e}")
        raise
    except Exception as e:
        print(f"\n⚠️  UNEXPECTED ERROR:")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        raise

# Example usage (uncomment to test):
# if __name__ == "__main__":
#     print("Querying LLM...")
#     response = query_llm("What is the capital of France?")
#     print(f"\nLLM Response: {response}")