from configparser import ConfigParser
from argparse import ArgumentParser
import time
import signal
import sys

from utils.server_registration import get_cache_server
from utils.config import Config
from crawler import Crawler

def signal_handler(sig, frame):
    print("\nCrawler interrupted by user. Generating report...")
    from scraper import generate_report
    report = generate_report()
    with open("crawl_report.txt", "w") as f:
        f.write(report)
    print("Crawl report has been saved to crawl_report.txt")
    sys.exit(0)

def main(config_file, restart):
    # Set up signal handler for graceful interruption
    signal.signal(signal.SIGINT, signal_handler)
    
    cparser = ConfigParser()
    cparser.read(config_file)
    config = Config(cparser)
    config.cache_server = get_cache_server(config, restart)
    
    print("Starting crawler...")
    print("Press Ctrl+C to stop the crawler and generate report")
    print("Monitoring progress...")
    
    crawler = Crawler(config, restart)
    crawler.start()
    
    # If crawler finishes naturally
    print("\nCrawler has finished naturally. Generating report...")
    from scraper import generate_report
    report = generate_report()
    with open("crawl_report.txt", "w") as f:
        f.write(report)
    print("Crawl report has been saved to crawl_report.txt")

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--restart", action="store_true", default=False)
    parser.add_argument("--config_file", type=str, default="config.ini")
    args = parser.parse_args()
    main(args.config_file, args.restart)
