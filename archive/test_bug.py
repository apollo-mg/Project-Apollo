import requests

def fetch_data(url):
    response = requests.get(url)
    return response.json()

def main():
    print("Starting data fetch...")
    data = fetch_data("https://api.example.com/data")
    print(data)

if __name__ == "__main__":
    main()
