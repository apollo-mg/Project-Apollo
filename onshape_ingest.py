import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import trafilatura
import hashlib
import logging
from modules.vdb import get_vector_store, get_text_splitter, Document

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("onshape_ingest.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OnShapeIngest")

def get_links(url, domain_filter=True):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = set()
        domain = urlparse(url).netloc
        path_prefix = urlparse(url).path
        for a in soup.find_all('a', href=True):
            full_url = urljoin(url, a['href'])
            full_url = full_url.split('#')[0]
            parsed = urlparse(full_url)
            if domain_filter:
                if parsed.netloc == domain and parsed.path.startswith(path_prefix):
                    links.add(full_url)
            else:
                links.add(full_url)
        return sorted(list(links))
    except Exception as e:
        logger.error(f"Error getting links from {url}: {e}")
        return []

def ingest_url(url, vector_store, text_splitter, category):
    logger.info(f"Ingesting {category}: {url}")
    
    # Use URL as hash/identifier
    url_id = hashlib.sha256(url.encode()).hexdigest()
    
    try:
        existing_docs = vector_store.get(where={"url_id": url_id}, limit=1)
        if existing_docs['ids']:
            logger.info(f"Skipped: {url} already indexed.")
            return False
    except: pass

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        logger.error(f"Failed to fetch {url}")
        return False
    
    content = trafilatura.extract(downloaded)
    if not content:
        logger.error(f"Failed to extract content from {url}")
        return False

    doc = Document(page_content=content, metadata={
        "source": url,
        "url_id": url_id,
        "type": "onshape_doc",
        "category": category
    })
    
    chunks = text_splitter.split_documents([doc])
    if chunks:
        vector_store.add_documents(documents=chunks)
        logger.info(f"Indexed {len(chunks)} chunks from {url}")
        return True
    return False

def main():
    vector_store = get_vector_store()
    text_splitter = get_text_splitter()

    targets = [
        {"url": "https://cad.onshape.com/FsDoc/", "category": "FeatureScript"},
        {"url": "https://onshape-public.github.io/docs/", "category": "API"}
    ]

    all_links = []
    for target in targets:
        links = get_links(target['url'])
        for link in links:
            all_links.append({"url": link, "category": target['category']})
        # Include the index page itself
        all_links.append({"url": target['url'], "category": target['category']})

    logger.info(f"Found total {len(all_links)} unique pages to ingest.")

    count = 0
    for item in all_links:
        if ingest_url(item['url'], vector_store, text_splitter, item['category']):
            count += 1
    
    logger.info(f"Finished ingestion. Successfully indexed {count} new pages.")

if __name__ == "__main__":
    main()
