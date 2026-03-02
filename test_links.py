import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def get_links(url, domain_filter=True):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = set()
        domain = urlparse(url).netloc
        for a in soup.find_all('a', href=True):
            full_url = urljoin(url, a['href'])
            # Remove fragments
            full_url = full_url.split('#')[0]
            if domain_filter:
                if urlparse(full_url).netloc == domain:
                    links.add(full_url)
            else:
                links.add(full_url)
        return sorted(list(links))
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    fs_links = get_links("https://cad.onshape.com/help/Content/")
    print(f"Found {len(fs_links)} links in FeatureScript Doc")
    for link in fs_links[:10]:
        print(link)
