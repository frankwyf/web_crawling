import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

RED_COLOR = '\033[91m'
BLUE_COLOR = '\033[94m'
YELLOW_COLOR = '\033[93m'
GREEN_COLOR = '\033[92m'
GREY_COLOR = '\033[90m'
END_COLOR = '\033[0m'

DEFAULT_BASE_URL = 'https://quotes.toscrape.com'
DEFAULT_POLITENESS_INTERVAL = 1.0
DEFAULT_INDEX_FILE = 'invert_index.json'
DEFAULT_WEB_HOST = '127.0.0.1'
DEFAULT_WEB_PORT = 8000
REQUEST_TIMEOUT = 15
REQUEST_HEADERS = {
    'User-Agent': 'PortfolioWebCrawler/1.0 (+https://quotes.toscrape.com)'
}

index = {}


def fetch_page(url, politeness_interval):
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        time.sleep(politeness_interval)
    except requests.RequestException as e:
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


def crawl_website(base_url, politeness_interval):
    pages = []
    page_urls = []
    page_links = []
    seen_urls = set()
    page_url = base_url

    def append_page(target_url):
        if target_url in seen_urls:
            return None

        html_content = fetch_page(target_url, politeness_interval)
        if not html_content:
            return None

        words, links = extract_text(html_content)
        if target_url.endswith('/login'):
            words.append('login')

        pages.append(words)
        page_urls.append(target_url)
        page_links.append(links)
        seen_urls.add(target_url)
        return html_content

    with tqdm(desc='Crawling Pages', dynamic_ncols=True) as pbar:
        append_page(base_url + '/login')

        while page_url:
            html_content = append_page(page_url)
            if not html_content:
                break

            pbar.update(1)
            pbar.set_postfix_str(f"Pages Crawled: {len(pages)}")

            soup = BeautifulSoup(html_content, 'html.parser')

            span_tags = soup.find_all('span')
            for span in span_tags:
                quote_a_tags = span.find_all('a', href=True)
                for anchor in quote_a_tags:
                    span_url = base_url + anchor['href']
                    if append_page(span_url):
                        pbar.update(1)

            quote_tags = soup.find_all('div', class_='tags')
            for quote in quote_tags:
                side_a_tags = quote.find_all('a', href=True)
                for anchor in side_a_tags:
                    quote_url = base_url + anchor['href']
                    if append_page(quote_url):
                        pbar.update(1)

            next_page_link = soup.find('li', class_='next')
            page_url = base_url + next_page_link.a['href'] if next_page_link else None

    return pages, page_urls, page_links


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
