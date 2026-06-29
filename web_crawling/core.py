import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util import Retry

try:
    import httpx
except ImportError:  # pragma: no cover - handled by runtime guard
    httpx = None

RED_COLOR = '\033[91m'
BLUE_COLOR = '\033[94m'
YELLOW_COLOR = '\033[93m'
GREEN_COLOR = '\033[92m'
GREY_COLOR = '\033[90m'
END_COLOR = '\033[0m'

DEFAULT_BASE_URL = 'https://quotes.toscrape.com'
DEFAULT_POLITENESS_INTERVAL = 1.0
DEFAULT_INDEX_FILE = 'invert_index.json'
DEFAULT_CRAWL_REPORT_FILE = 'crawl_report.json'
DEFAULT_WEB_HOST = '127.0.0.1'
DEFAULT_WEB_PORT = 8000
REQUEST_TIMEOUT = 15
CONNECT_TIMEOUT = 5
REQUEST_HEADERS = {
    'User-Agent': 'PortfolioWebCrawler/1.0 (+https://quotes.toscrape.com)'
}
MAX_RETRIES = 3
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
DEFAULT_CRAWL_MODE = 'sync'
DEFAULT_ASYNC_CONCURRENCY = 8

index = {}


@dataclass
class CrawlStats:
    started_at: str
    finished_at: str
    base_url: str
    pages_crawled: int
    pages_failed: int
    total_tokens: int
    unique_tokens: int
    avg_tokens_per_page: float
    discovered_links: int
    sitemap_seeds: int
    duration_seconds: float


LAST_CRAWL_STATS: Optional[CrawlStats] = None


def _build_session():
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        backoff_factor=0.4,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods={'GET', 'HEAD'},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update(REQUEST_HEADERS)
    return session


def _normalize_url(base_url, href):
    if not href:
        return None
    if href.startswith('#'):
        return None
    normalized = urljoin(base_url, href)
    parsed = urlparse(normalized)
    if parsed.scheme not in {'http', 'https'}:
        return None
    clean_path = parsed.path or '/'
    clean = f'{parsed.scheme}://{parsed.netloc}{clean_path}'
    return clean.rstrip('/') or clean


def _is_same_site(base_url, candidate):
    return urlparse(base_url).netloc == urlparse(candidate).netloc


def _extract_internal_links(html_content, current_url, base_url):
    soup = BeautifulSoup(html_content, 'html.parser')
    links = set()
    for anchor in soup.find_all('a', href=True):
        normalized = _normalize_url(current_url, anchor['href'])
        if not normalized:
            continue
        if _is_same_site(base_url, normalized):
            links.add(normalized)
    return links


def _sitemap_candidates(base_url, session):
    sitemap_url = _normalize_url(base_url, '/sitemap.xml')
    if not sitemap_url:
        return set()

    try:
        response = session.get(sitemap_url, timeout=(CONNECT_TIMEOUT, REQUEST_TIMEOUT))
        if response.status_code >= 400:
            return set()
        soup = BeautifulSoup(response.text, 'xml')
        urls = set()
        for loc in soup.find_all('loc'):
            if not loc.text:
                continue
            normalized = _normalize_url(base_url, loc.text.strip())
            if normalized and _is_same_site(base_url, normalized):
                urls.add(normalized)
        return urls
    except requests.RequestException:
        return set()


def fetch_page(url, politeness_interval, session=None):
    http = session or _build_session()
    try:
        response = http.get(url, timeout=(CONNECT_TIMEOUT, REQUEST_TIMEOUT))
        response.raise_for_status()
        time.sleep(politeness_interval)
    except requests.RequestException as e:
        print(RED_COLOR + f"Failed to fetch page: {url}" + END_COLOR)
        print(e)
        return None
    return response.text


async def fetch_page_async(url, politeness_interval, client):
    try:
        response = await client.get(url, timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT))
        response.raise_for_status()
        if politeness_interval > 0:
            await asyncio.sleep(politeness_interval)
    except httpx.HTTPError as e:
        print(RED_COLOR + f"Failed to fetch page: {url}" + END_COLOR)
        print(e)
        return None
    return response.text


def extract_text(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    outwards_links = soup.find_all('a', href=True)
    short_text = soup.find_all('span', class_='text')
    detailed_text = soup.find_all('div', class_='author-description')
    tags = soup.find_all('a')
    by_author = soup.find_all('small', class_='author')
    author_born_date = soup.find_all('span', class_='author-born-date')
    author_born_location = soup.find_all('span', class_='author-born-location')
    author = soup.find_all('h3', class_='author-title')
    detail_title = soup.find_all('strong')
    top = soup.find_all('h2')
    footer = soup.find_all('p', class_='text-muted')

    made_with = []
    copyright_node = soup.find('p', class_='copyright')
    if copyright_node is not None:
        made_with = copyright_node.get_text(' ', strip=True).split()

    tags_divs = soup.find_all('div', class_='tags')
    small_tag_names = []
    for tags_div in tags_divs:
        for text in tags_div.strings:
            if 'Tags:' in text:
                tags_header = text.strip()
                small_tag_names.append(tags_header)
                break

    span_tag = soup.find_all('span')
    by_whom = []
    for span in span_tag:
        for text in span.strings:
            if 'by' in text:
                tags_header = text.strip()
                by_whom.append(tags_header)
                break

    login_labels = soup.find_all('label')
    text_short = ' '.join(tag.get_text() for tag in short_text)
    text_detail = ' '.join(tag.get_text() for tag in detailed_text)
    text_tag = ' '.join(tag.get_text() for tag in tags)
    text_author = ' '.join(tag.get_text() for tag in by_author)
    text_born_date = ' '.join(tag.get_text() for tag in author_born_date)
    text_born_location = ' '.join(tag.get_text() for tag in author_born_location)
    text_author_title = ' '.join(tag.get_text() for tag in author)
    text_top_title = ' '.join(tag.get_text() for tag in top)
    text_footer = ' '.join(tag.get_text() for tag in footer)
    text_strong = ' '.join(tag.get_text() for tag in detail_title)
    made_with_text = ' '.join(tag for tag in made_with)
    text_small_tag_names = ' '.join(tag for tag in small_tag_names)
    by_whom_text = ' '.join(tag for tag in by_whom)
    text_login_labels = ' '.join(tag.get_text() for tag in login_labels)

    combined_text = (
        text_short + ' ' + text_detail + ' ' + text_tag + ' ' + text_author + ' ' + text_born_date + ' '
        + text_born_location + ' ' + text_author_title + ' ' + text_top_title + ' ' + text_footer + ' '
        + made_with_text + ' ' + text_strong + ' ' + text_small_tag_names + ' ' + by_whom_text + ' '
        + text_login_labels
    )
    processed_text = re.sub(r'(?<=\d),(?=\d)', '', combined_text)
    words = re.findall(r'\b[\w\d\u4e00-\u9fa5\u3040-\u30ff\u0400-\u04ff]+\b', processed_text.lower())
    return list(words), len(outwards_links)


def crawl_website(base_url, politeness_interval, max_pages=150, include_sitemap=True):
    global LAST_CRAWL_STATS

    pages = []
    page_urls = []
    page_links = []
    seen_urls = set()
    failed_urls = set()
    pending_urls = []
    total_discovered_links = 0
    started_at = time.perf_counter()
    started_stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    session = _build_session()

    def append_page(target_url):
        nonlocal total_discovered_links
        if target_url in seen_urls:
            return None

        html_content = fetch_page(target_url, politeness_interval, session=session)
        if not html_content:
            failed_urls.add(target_url)
            return None

        words, links = extract_text(html_content)
        if target_url.endswith('/login') or '/login/' in target_url:
            words.append('login')

        pages.append(words)
        page_urls.append(target_url)
        page_links.append(links)
        seen_urls.add(target_url)

        internal_links = _extract_internal_links(html_content, target_url, base_url)
        total_discovered_links += len(internal_links)
        for item in sorted(internal_links):
            if item not in seen_urls:
                pending_urls.append(item)
        return html_content

    seed_url = _normalize_url(base_url, base_url) or base_url.rstrip('/')
    login_url = _normalize_url(base_url, '/login')
    if login_url:
        pending_urls.append(login_url)
    pending_urls.append(seed_url)

    if include_sitemap:
        for item in sorted(_sitemap_candidates(base_url, session)):
            pending_urls.append(item)

    deduped_queue = []
    seen_pending = set()
    for item in pending_urls:
        if item and item not in seen_pending:
            deduped_queue.append(item)
            seen_pending.add(item)
    pending_urls = deduped_queue

    sitemap_seed_count = max(len(pending_urls) - 2, 0)

    with tqdm(desc='Crawling Pages', dynamic_ncols=True) as pbar:
        while pending_urls and len(pages) < max_pages:
            page_url = pending_urls.pop(0)
            html_content = append_page(page_url)
            if not html_content:
                continue
            pbar.update(1)
            pbar.set_postfix_str(f"Pages Crawled: {len(pages)}")

    finished_stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    duration_seconds = round(time.perf_counter() - started_at, 3)
    total_tokens = sum(len(page) for page in pages)
    unique_tokens = len({token for page in pages for token in page}) if pages else 0
    avg_tokens = round(total_tokens / len(pages), 3) if pages else 0.0

    LAST_CRAWL_STATS = CrawlStats(
        started_at=started_stamp,
        finished_at=finished_stamp,
        base_url=base_url,
        pages_crawled=len(pages),
        pages_failed=len(failed_urls),
        total_tokens=total_tokens,
        unique_tokens=unique_tokens,
        avg_tokens_per_page=avg_tokens,
        discovered_links=total_discovered_links,
        sitemap_seeds=sitemap_seed_count,
        duration_seconds=duration_seconds,
    )

    session.close()
    return pages, page_urls, page_links


async def crawl_website_async(
    base_url,
    politeness_interval,
    max_pages=150,
    include_sitemap=True,
    concurrency=DEFAULT_ASYNC_CONCURRENCY,
):
    global LAST_CRAWL_STATS

    if httpx is None:
        raise RuntimeError('Async crawl mode requires httpx. Install it with: pip install httpx')
    if concurrency < 1:
        raise ValueError('concurrency must be >= 1')

    pages = []
    page_urls = []
    page_links = []
    seen_urls = set()
    failed_urls = set()
    pending_urls = []
    in_flight = set()
    total_discovered_links = 0
    started_at = time.perf_counter()
    started_stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    seed_url = _normalize_url(base_url, base_url) or base_url.rstrip('/')
    login_url = _normalize_url(base_url, '/login')
    if login_url:
        pending_urls.append(login_url)
    pending_urls.append(seed_url)

    if include_sitemap:
        sitemap_session = _build_session()
        try:
            for item in sorted(_sitemap_candidates(base_url, sitemap_session)):
                pending_urls.append(item)
        finally:
            sitemap_session.close()

    deduped_queue = []
    seen_pending = set()
    for item in pending_urls:
        if item and item not in seen_pending:
            deduped_queue.append(item)
            seen_pending.add(item)
    pending_urls = deduped_queue

    sitemap_seed_count = max(len(pending_urls) - 2, 0)

    async with httpx.AsyncClient(headers=REQUEST_HEADERS, follow_redirects=True) as client:
        with tqdm(desc='Crawling Pages (async)', dynamic_ncols=True) as pbar:
            while pending_urls and len(pages) < max_pages:
                batch = []
                while pending_urls and len(batch) < concurrency and len(pages) + len(batch) < max_pages:
                    candidate = pending_urls.pop(0)
                    if candidate in seen_urls or candidate in in_flight:
                        continue
                    batch.append(candidate)
                    in_flight.add(candidate)

                if not batch:
                    continue

                batch_results = await asyncio.gather(
                    *(fetch_page_async(target, politeness_interval, client) for target in batch)
                )

                for target_url, html_content in zip(batch, batch_results):
                    in_flight.discard(target_url)
                    if not html_content:
                        failed_urls.add(target_url)
                        continue

                    words, links = extract_text(html_content)
                    if target_url.endswith('/login') or '/login/' in target_url:
                        words.append('login')

                    pages.append(words)
                    page_urls.append(target_url)
                    page_links.append(links)
                    seen_urls.add(target_url)

                    internal_links = _extract_internal_links(html_content, target_url, base_url)
                    total_discovered_links += len(internal_links)
                    for item in sorted(internal_links):
                        if item not in seen_urls and item not in in_flight:
                            pending_urls.append(item)

                    pbar.update(1)
                    pbar.set_postfix_str(f"Pages Crawled: {len(pages)}")

    finished_stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    duration_seconds = round(time.perf_counter() - started_at, 3)
    total_tokens = sum(len(page) for page in pages)
    unique_tokens = len({token for page in pages for token in page}) if pages else 0
    avg_tokens = round(total_tokens / len(pages), 3) if pages else 0.0

    LAST_CRAWL_STATS = CrawlStats(
        started_at=started_stamp,
        finished_at=finished_stamp,
        base_url=base_url,
        pages_crawled=len(pages),
        pages_failed=len(failed_urls),
        total_tokens=total_tokens,
        unique_tokens=unique_tokens,
        avg_tokens_per_page=avg_tokens,
        discovered_links=total_discovered_links,
        sitemap_seeds=sitemap_seed_count,
        duration_seconds=duration_seconds,
    )

    return pages, page_urls, page_links


def crawl_website_by_mode(
    base_url,
    politeness_interval,
    max_pages=150,
    include_sitemap=True,
    crawl_mode=DEFAULT_CRAWL_MODE,
    concurrency=DEFAULT_ASYNC_CONCURRENCY,
):
    if crawl_mode == 'async':
        return asyncio.run(
            crawl_website_async(
                base_url,
                politeness_interval,
                max_pages=max_pages,
                include_sitemap=include_sitemap,
                concurrency=concurrency,
            )
        )
    return crawl_website(base_url, politeness_interval, max_pages=max_pages, include_sitemap=include_sitemap)


def build_index(pages, invert_index_file, page_urls, outward_links):
    file_index = {}
    total_lines = sum(len(page_content) for page_content in pages)
    with tqdm(total=total_lines, desc='Building Inverted Index', dynamic_ncols=True) as pbar:
        for i, page_content in enumerate(pages):
            for j, word in enumerate(page_content):
                if word not in file_index:
                    file_index[word] = []
                word_doc = next((doc for doc in file_index[word] if doc['Page'] == i), None)
                if word_doc:
                    word_doc['Frequency'] += 1
                    word_doc['Positions'].append(j)
                else:
                    file_index[word].append(
                        {
                            'Page': i,
                            'Frequency': 1,
                            'URL': page_urls[i],
                            'Positions': [j],
                            'Links': outward_links[i],
                        }
                    )
                pbar.update(1)
                pbar.set_postfix_str(f"Processed {pbar.n}/{total_lines} Tokens")
    print(GREEN_COLOR + 'Inverted index of ' + str(len(file_index)) + ' words built successfully.' + END_COLOR)

    with open(invert_index_file, 'w', encoding='utf-8') as f:
        json.dump(file_index, f, ensure_ascii=False, indent=2)

    return file_index


def load_index_json(invert_index_file):
    global index
    with open(invert_index_file, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    index.clear()
    index.update(loaded)
    return index


def print_index(word, index_data):
    word = word.lower()
    print(f"Searching for '{word}' in the index...")

    if word in index_data:
        entries = index_data[word]
        entries = [(item['URL'], item['Frequency']) for item in entries]
        if entries:
            print(f"Pages containing the word '{word}':")
            print(GREEN_COLOR + '************************************************************************' + END_COLOR)
            print(entries)
            print(GREEN_COLOR + '************************************************************************' + END_COLOR)
        else:
            print(RED_COLOR + f"No pages found for '{word}' in the index." + END_COLOR)
    else:
        print(RED_COLOR + f"'{word}' not found in index." + END_COLOR)


def page_rank(page_set, case):
    ranked_result = set()
    if case == 0:
        for doc in page_set:
            final_score = 0
            for item in page_set:
                if doc[0] != item[0]:
                    score = 1 / (len(page_set) * max(item[3], 1))
                    final_score += score
            ranked_result.add((doc[0], doc[1], doc[2], final_score))
        ranked_result = sorted(ranked_result, key=lambda x: (-x[2], -x[3], x[0]))
    if case == 1:
        for docs in page_set:
            final_score = 0
            for item in page_set:
                if docs[0] != item[0]:
                    score = 1 / (len(page_set) * max(item[4], 1))
                    final_score += score
            ranked_result.add((docs[0], docs[1], docs[2], docs[3], final_score))
        ranked_result = sorted(ranked_result, key=lambda x: (-x[2], -x[4], x[0]))
    if case == 2:
        for docs in page_set:
            final_score = 0
            for item in page_set:
                if docs[0] != item[0]:
                    score = 1 / (len(page_set) * max(item[3], 1))
                    final_score += score
            ranked_result.add((docs[0], docs[1], docs[2], final_score, docs[4]))
    return ranked_result


def each_word_rank(item, query_words):
    page_id, url, frequency, score, word = item
    word_order = query_words.index(word)
    return word_order, -frequency, -score, page_id


def search_query(query, index_data):
    query_words = query.lower().split()
    if not query_words:
        return {'type': 'empty', 'query': query, 'ranked_pages': []}

    if len(query_words) == 1:
        single_query_result = set()
        if query_words[0] in index_data:
            for doc in index_data[query_words[0]]:
                single_query_result.add((doc['Page'], doc['URL'], doc['Frequency'], doc['Links']))

        ranked_pages = page_rank(single_query_result, 0) if single_query_result else []
        return {
            'type': 'single',
            'query': query,
            'query_words': query_words,
            'ranked_pages': ranked_pages,
        }

    phrase_result = set()
    any_order_result = set()
    each_query_result = set()

    for word in query_words:
        if word in index_data:
            for doc in index_data[word]:
                each_query_result.add((doc['Page'], doc['URL'], doc['Frequency'], doc['Links'], word))

    first_word = query_words[0]
    if first_word in index_data:
        for doc in index_data[first_word]:
            phrase_result.add((doc['Page'], doc['URL'], doc['Frequency'], tuple(doc['Positions']), doc['Links']))

        for word in query_words[1:]:
            if word in index_data:
                word_docs = set()
                for doc in index_data[word]:
                    word_docs.add((doc['Page'], doc['URL'], doc['Frequency'], tuple(doc['Positions']), doc['Links']))

                for doc in phrase_result:
                    occurrence = doc[2]
                    for item in word_docs:
                        if doc[0] == item[0]:
                            occurrence += item[2]
                    if occurrence != doc[2]:
                        any_order_result.add((doc[0], doc[1], occurrence, doc[4]))

        for word in query_words[1:]:
            if word in index_data:
                word_docs = set()
                for doc in index_data[word]:
                    word_docs.add((doc['Page'], doc['URL'], doc['Frequency'], tuple(doc['Positions']), doc['Links']))

                filtered_docs = set()
                for result_doc in phrase_result:
                    phrase_count = 0
                    for word_doc in word_docs:
                        if result_doc[0] == word_doc[0]:
                            for item in result_doc[3]:
                                for item2 in word_doc[3]:
                                    if item + 1 == item2:
                                        phrase_count += 1
                                        for item3 in word_doc[3]:
                                            if item2 + 1 == item3:
                                                phrase_count += 1

                    if phrase_count != 0:
                        filtered_docs.add((result_doc[0], result_doc[1], phrase_count, result_doc[3], result_doc[4]))
                phrase_result = filtered_docs

    duplicate_any_order = set()
    duplicate_each_query = set()

    for doc in phrase_result:
        for doc2 in any_order_result:
            if doc[0] == doc2[0] and doc[0] not in duplicate_any_order:
                duplicate_any_order.add(doc2[0])

    for doc in phrase_result:
        for doc3 in each_query_result:
            if doc[0] == doc3[0] and doc[0] not in duplicate_each_query:
                duplicate_each_query.add(doc3[0])

    for doc in any_order_result:
        for doc2 in each_query_result:
            if doc[0] == doc2[0] and doc[0] not in duplicate_each_query:
                duplicate_each_query.add(doc[0])

    any_order_result = [doc for doc in any_order_result if doc[0] not in duplicate_any_order]
    each_query_result = [doc for doc in each_query_result if doc[0] not in duplicate_each_query]

    phrase_result = page_rank(phrase_result, 1)
    any_order_result = page_rank(any_order_result, 0)
    each_query_result = page_rank(each_query_result, 2)
    each_query_result = sorted(each_query_result, key=lambda x: each_word_rank(x, query_words))

    return {
        'type': 'phrase',
        'query': query,
        'query_words': query_words,
        'phrase_result': phrase_result,
        'any_order_result': any_order_result,
        'each_query_result': each_query_result,
    }


def find_pages(query, index_data):
    print(f"Searching for '{query}' in the index...")
    result = search_query(query, index_data)
    query_words = result.get('query_words', [])

    if result['type'] == 'single':
        print(GREEN_COLOR + '*****************************************************************************************' + END_COLOR)
        if result['ranked_pages']:
            print(RED_COLOR + f"Pages containing the word '{query_words[0]}':" + END_COLOR)
            for page_id, url, frequency, links in result['ranked_pages']:
                print(f"Page {page_id}: {url}, Occurrence: {frequency}, Score: {links}")
        else:
            print(f"No pages found containing the word '{query_words[0]}'.")
        print(GREEN_COLOR + '*****************************************************************************************' + END_COLOR)
    else:
        phrase_result = result['phrase_result']
        any_order_result = result['any_order_result']
        each_query_result = result['each_query_result']

        print(GREEN_COLOR + '******************************************************************************************' + END_COLOR)
        if phrase_result:
            print(RED_COLOR + f"Pages containing phrase (conjunctive process) '{query}':" + END_COLOR)
            for page_id, url, frequency, position, links in phrase_result:
                print(f"Page {page_id}: {url}; Occurrence: {frequency}; Score: {links}")
        else:
            print(f"No pages found containing phrase (conjunctive process) '{query}'.")
        print(GREEN_COLOR + '******************************************************************************************' + END_COLOR)

        print(BLUE_COLOR + '******************************************************************************************' + END_COLOR)
        if any_order_result:
            print(RED_COLOR + f"Pages containing phrase (term at a time) in '{query}':" + END_COLOR)
            for page_id, url, frequency, links in any_order_result:
                print(f"Page {page_id}: {url}; Occurrence: {frequency}; Score: {links}")
        else:
            print(f"No pages found containing phrase (term at a time) in '{query}'.")
        print(BLUE_COLOR + '******************************************************************************************' + END_COLOR)

        print(GREY_COLOR + '******************************************************************************************' + END_COLOR)
        if each_query_result:
            print(RED_COLOR + f"Pages containing each word in '{query}':" + END_COLOR)
            for page_id, url, frequency, links, word in each_query_result:
                print(f"Term: {word}; Page {page_id}: {url}; Occurrence: {frequency}; Score: {links}")
        else:
            print(f"No pages found containing each word in '{query}'.")
        print(GREY_COLOR + '******************************************************************************************' + END_COLOR)


def ensure_index_loaded(index_path):
    if len(index) == 0:
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Index file not found: {index_path}")
        load_index_json(index_path)


def get_last_crawl_stats():
    if LAST_CRAWL_STATS is None:
        return None
    return {
        'started_at': LAST_CRAWL_STATS.started_at,
        'finished_at': LAST_CRAWL_STATS.finished_at,
        'base_url': LAST_CRAWL_STATS.base_url,
        'pages_crawled': LAST_CRAWL_STATS.pages_crawled,
        'pages_failed': LAST_CRAWL_STATS.pages_failed,
        'total_tokens': LAST_CRAWL_STATS.total_tokens,
        'unique_tokens': LAST_CRAWL_STATS.unique_tokens,
        'avg_tokens_per_page': LAST_CRAWL_STATS.avg_tokens_per_page,
        'discovered_links': LAST_CRAWL_STATS.discovered_links,
        'sitemap_seeds': LAST_CRAWL_STATS.sitemap_seeds,
        'duration_seconds': LAST_CRAWL_STATS.duration_seconds,
    }


def generate_crawl_report(report_path, pages, page_urls, page_links, index_data, crawl_stats):
    top_terms = []
    for term, postings in index_data.items():
        total_frequency = sum(item.get('Frequency', 0) for item in postings)
        top_terms.append({'term': term, 'total_frequency': total_frequency})
    top_terms = sorted(top_terms, key=lambda x: (-x['total_frequency'], x['term']))[:30]

    page_summaries = []
    for idx, url in enumerate(page_urls):
        page_summaries.append(
            {
                'page': idx,
                'url': url,
                'token_count': len(pages[idx]),
                'outgoing_links': page_links[idx],
            }
        )

    page_summaries = sorted(page_summaries, key=lambda x: (-x['token_count'], -x['outgoing_links']))[:20]

    report = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'crawl_stats': crawl_stats,
        'index_stats': {
            'unique_terms': len(index_data),
            'total_pages': len(page_urls),
            'total_tokens': sum(len(doc) for doc in pages),
        },
        'top_terms': top_terms,
        'top_pages': page_summaries,
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report
