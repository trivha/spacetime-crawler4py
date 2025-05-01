import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urldefrag
from collections import Counter, defaultdict

# global trackers
word_counter = Counter()
page_word_counts = {}
unique_urls = set()
subdomain_counts = defaultdict(set)
longest_page = {"url": "", "count": 0}

# stopwords
with open("stopwords.txt") as f:
    stopwords = set(word.strip().lower() for word in f.readlines())

# helpers
def extract_visible_text(soup):
    for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        element.decompose()
    return soup.get_text(separator=' ')

def tokenize(text):
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    return [word for word in words if word not in stopwords]

def process_html_section(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    text = extract_visible_text(soup)
    words = tokenize(text)

    if len(words) < 20:
        return

    clean_url, _ = urldefrag(url)
    unique_urls.add(clean_url)
    page_word_counts[clean_url] = len(words)
    word_counter.update(words)

    if len(words) > longest_page["count"]:
        longest_page["url"] = clean_url
        longest_page["count"] = len(words)

    parsed = urlparse(clean_url)
    subdomain_counts[parsed.netloc].add(clean_url)

def parse_saved_bundles():
    directory = "saved_pages"
    if not os.path.exists(directory):
        print("No saved_pages directory found.")
        return

    for filename in os.listdir(directory):
        if filename.endswith(".htmlbundle"):
            with open(os.path.join(directory, filename), 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            sections = re.split(r'<!-- START PAGE: (.*?) -->', content)
            # format: ['', url1, html1, url2, html2, ...]
            for i in range(1, len(sections) - 1, 2):
                url = sections[i].strip()
                html = sections[i + 1].split("<!-- END PAGE", 1)[0]
                process_html_section(html, url)

    # final report
    print("\n--- POST-BUNDLE REPORT ---\n")
    print(f"1. Number of unique pages: {len(unique_urls)}")
    print(f"2. Longest page: {longest_page['url']} with {longest_page['count']} words")
    print("3. Top 50 most common words:")
    for word, count in word_counter.most_common(50):
        print(f"   {word}: {count}")
    print("4. Subdomains and their page counts:")
    for sub, urls in sorted(subdomain_counts.items()):
        print(f"   {sub}, {len(urls)}")

if __name__ == "__main__":
    parse_saved_bundles()
