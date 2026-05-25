import requests

def get_huggingface_model_info(model_id):
    url = f"https://huggingface.co/api/models/{model_id}"
    response = requests.get(url)
    if response.status_code == 200:
        print(f"Model {model_id} found!")
        return response.json()
    else:
        print(f"Failed to find model: {response.status_code}")
        return None

get_huggingface_model_info("mradermacher/Nemotron-Cascade-2-30B-A3B-i1-GGUF")
