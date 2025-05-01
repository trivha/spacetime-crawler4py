from collections import Counter
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urldefrag, urljoin
import re, os, hashlib

# --- Globals for tracking ---
word_counter = Counter()
page_word_counts = {}
dynamic_traps = set()
subdomain_counts = {}
unique_urls = set()
longest_page = {"url": "", "count": 0}

# --- Directory for saving HTML pages ---
SAVE_DIR = "saved_pages"
os.makedirs(SAVE_DIR, exist_ok=True)

# --- Load stop words ---
with open("stopwords.txt") as f:
    stopwords = set(word.strip().lower() for word in f.readlines())

def compute_checksum(content):
        return hashlib.sha256(content).hexdigest()
# --- Batching Config ---
BUNDLE_SIZE = 20
BUNDLE_FILE_INDEX = 0
BUNDLE_PAGE_COUNT = 0
BUNDLE_PATH = os.path.join(SAVE_DIR, f"bundle_{BUNDLE_FILE_INDEX}.htmlbundle")

def save_page_locally(url, content):
    global BUNDLE_PAGE_COUNT, BUNDLE_FILE_INDEX, BUNDLE_PATH

    checksum = compute_checksum(content)
    with open(os.path.join(SAVE_DIR, "checksums.txt"), "a") as cf:
        cf.write(f"{checksum} {url}\n")



    if BUNDLE_PAGE_COUNT >= BUNDLE_SIZE:
        BUNDLE_FILE_INDEX += 1
        BUNDLE_PAGE_COUNT = 0
        BUNDLE_PATH = os.path.join(SAVE_DIR, f"bundle_{BUNDLE_FILE_INDEX}.htmlbundle")

    with open(BUNDLE_PATH, "ab") as f:
        f.write(f"\n<!-- START PAGE: {url} -->\n".encode('utf-8'))
        f.write(content)
        f.write(f"\n<!-- END PAGE: {url} -->\n".encode('utf-8'))

    BUNDLE_PAGE_COUNT += 1



# --- Trap Helpers ---
def record_bad_page(url):
    parsed = urlparse(url)
    base = parsed.scheme + "://" + parsed.netloc + parsed.path.rsplit('/', 1)[0] + '/'
    dynamic_traps.add(base)

def is_dynamic_trap(url):
    for base in dynamic_traps:
        if url.startswith(base):
            print(f"Dynamically detected trap, skipping URL: {url}")
            return True
    return False

def is_trap(url):
    trap_patterns = [
        r'calendar', r'event', r'events', r'/?page=\d+',
        r'/?year=\d{4}', r'/?month=\d{1,2}', r'/?day=\d{1,2}',
        r'/?view=archive', r'/?sort=', r'sessionid=',
        r'utm_', r'replytocom=', r'doku\.php',
        r'tribe-bar-date', r'ical', r'outlook-ical', r'eventdisplay', r'eventdate',
        r'/html_oopsc/', r'/risc/v063/html_oopsc/a\d+\.html'
    ]
    for pattern in trap_patterns:
        if re.search(pattern, url.lower()):
            print(f"Trap detected, skipping URL: {url}")
            return True
    return False

# --- Main Scraper Entry Point ---
def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    if resp.status != 200 or resp.raw_response is None:
        return []

    if len(resp.raw_response.content) > (2 * 1024 * 1024):
        print(f"Skipping large file: {url}")
        return []

    content_type = resp.raw_response.headers.get('Content-Type', '')
    if 'text/html' not in content_type:
        return []

    # Save HTML locally
    save_page_locally(url, resp.raw_response.content)

    links = set()

    try:
        soup = BeautifulSoup(resp.raw_response.content, 'html.parser')
        text = extract_visible_text(soup)
        words = tokenize(text)

        if len(words) < 20:
            print(f"Skipping dead/low-info page: {url}")
            record_bad_page(url)
            return []

        clean_url, _ = urldefrag(url)
        unique_urls.add(clean_url)

        parsed = urlparse(url)
        subdomain = parsed.netloc
        subdomain_counts[subdomain] = subdomain_counts.get(subdomain, 0) + 1

        if len(words) > longest_page["count"]:
            longest_page["url"] = url
            longest_page["count"] = len(words)

        page_word_counts[url] = len(words)
        word_counter.update(words)

        MAX_LINKS_PER_PAGE = 1000
        for a_tag in soup.find_all('a', href=True):
            if len(links) >= MAX_LINKS_PER_PAGE:
                break
            href = a_tag['href']
            absolute_href = urljoin(resp.url, href)
            absolute_href, _ = urldefrag(absolute_href)

            if not (is_trap(absolute_href) or is_dynamic_trap(absolute_href)):
                links.add(absolute_href)

    except Exception as e:
        print(f"Error extracting links from {url}: {e}")

    return list(links)

# --- Utility Functions ---
def extract_visible_text(soup):
    for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        element.decompose()
    return soup.get_text(separator=' ')

def tokenize(text):
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    return [word for word in words if word not in stopwords]

def is_valid(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if not (parsed.netloc.endswith("ics.uci.edu") or
                parsed.netloc.endswith("cs.uci.edu") or
                parsed.netloc.endswith("informatics.uci.edu") or
                parsed.netloc.endswith("stat.uci.edu") or
                parsed.netloc == "today.uci.edu"):
            return False
        
        if parsed.netloc == "today.uci.edu" and not parsed.path.startswith("/department/information_computer_sciences"):
            return False
        if "doku.php" in url and any(param in url for param in ["rev=", "do=", "difftype", "ns="]):
            return False

        if re.search(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            r"|png|tiff?|mid|mp2|mp3|mp4"
            r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            r"|epub|dll|cnf|tgz|sha1"
            r"|thmx|mso|arff|rtf|jar|csv"
            r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False
        return True
    except TypeError:
        print("TypeError for", url)
        return False
