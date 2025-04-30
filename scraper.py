from collections import Counter
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urldefrag, urljoin
import re

# tracking for crawler
word_counter = Counter()        # Count words globally
page_word_counts = {}            # {url -> number of words}
dynamic_traps = set()            # Store dynamic trap bases

# for stop words
with open("stopwords.txt") as f:
    stopwords = set(word.strip().lower() for word in f.readlines())

# for dynamic traps

def record_bad_page(url):
    """Record the base URL of bad pages (too few words)."""
    parsed = urlparse(url)
    base = parsed.scheme + "://" + parsed.netloc + parsed.path.rsplit('/', 1)[0] + '/'
    dynamic_traps.add(base)

def is_dynamic_trap(url):
    """Check if URL starts with any recorded dynamic trap base."""
    for base in dynamic_traps:
        if url.startswith(base):
            print(f"Dynamically detected trap, skipping URL: {url}")
            return True
    return False

# main crawler function

def scraper(url, resp):
    """Main scraper function called by the crawler framework."""
    links = extract_next_links(url, resp)
    valid_links = [link for link in links if is_valid(link)]
    return valid_links

def extract_next_links(url, resp):
    """Extract hyperlinks from a page if it is valid and informative."""
    if resp.status != 200 or resp.raw_response is None:
        return []

    if len(resp.raw_response.content) > (2 * 1024 * 1024):  # 2MB size limit
        print(f"Skipping large file: {url}")
        return []

    content_type = resp.raw_response.headers.get('Content-Type', '')
    if 'text/html' not in content_type:
        return []

    links = set()

    try:
        soup = BeautifulSoup(resp.raw_response.content, 'html.parser')

        # Extract visible text and tokenize
        text = extract_visible_text(soup)
        words = tokenize(text)

        if len(words) < 20:  # Dead page detection
            print(f"Skipping dead/low-info page: {url}")
            record_bad_page(url)
            return []

        # Save word statistics
        page_word_counts[url] = len(words)
        word_counter.update(words)

        # Extract links (limit if needed)
        MAX_LINKS_PER_PAGE = 1000
        for a_tag in soup.find_all('a', href=True):
            if len(links) >= MAX_LINKS_PER_PAGE:
                break
            href = a_tag['href']
            absolute_href = urljoin(resp.url, href)
            absolute_href, _ = urldefrag(absolute_href)  # remove fragments

            if not (is_trap(absolute_href) or is_dynamic_trap(absolute_href)):
                links.add(absolute_href)

    except Exception as e:
        print(f"Error extracting links from {url}: {e}")

    return list(links)

def extract_visible_text(soup):
    """Remove non-content tags and get the visible text."""
    for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        element.decompose()
    visible_text = soup.get_text(separator=' ')
    return visible_text

def tokenize(text):
    """Tokenize text into words, lowercase them, and remove stopwords."""
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    return [word for word in words if word not in stopwords]

def is_valid(url):
    """Validate if a URL should be crawled based on domain and file type."""
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

        if re.search(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False

        return True

    except TypeError:
        print("TypeError for", url)
        return False

def is_trap(url):
    """Detect common static trap patterns manually."""
    trap_patterns = [
        r'calendar',
        r'event',
        r'events',
        r'/?page=\d+',
        r'/?year=\d{4}',
        r'/?month=\d{1,2}',
        r'/?day=\d{1,2}',
        r'/?view=archive',
        r'/?sort=',
        r'sessionid=',
        r'utm_',  # marketing tracking
        r'replytocom=',
        r'/html_oopsc/', 
        r'/risc/v063/html_oopsc/a\d+\.html'
    ]
    for pattern in trap_patterns:
        if re.search(pattern, url.lower()):
            print(f"Trap detected, skipping URL: {url}")
            return True
    return False
