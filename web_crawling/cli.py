import argparse
import os

from .core import (
    BLUE_COLOR,
    DEFAULT_BASE_URL,
    DEFAULT_INDEX_FILE,
    DEFAULT_POLITENESS_INTERVAL,
    DEFAULT_WEB_HOST,
    DEFAULT_WEB_PORT,
    END_COLOR,
    RED_COLOR,
    YELLOW_COLOR,
    build_index,
    crawl_website,
    ensure_index_loaded,
    find_pages,
    index,
    print_index,
)
from .webui import run_web_ui


def handle_command(command, index_path, base_url, politeness_interval):
    if command == 'build':
        pages_content, urls, num_links = crawl_website(base_url, politeness_interval)
        build_index(pages_content, index_path, urls, num_links)
        if os.path.exists(index_path):
            print(BLUE_COLOR + 'Inverted index built and saved successfully.' + END_COLOR)
        else:
            print(RED_COLOR + 'Failed to build the index.' + END_COLOR)
        return

    if command == 'load':
        ensure_index_loaded(index_path)
        print(BLUE_COLOR + 'Inverted index file loaded successfully.' + END_COLOR)
        return

    if command.startswith('print'):
        ensure_index_loaded(index_path)
        query_parts = command.split(' ')
        if len(query_parts) != 2:
            print(RED_COLOR + 'Phrase is not acceptable. Usage: print <word>' + END_COLOR)
            return
        print_index(query_parts[1], index)
        return

    if command.startswith('find'):
        ensure_index_loaded(index_path)
        if len(command.split(' ')) < 2:
            print(RED_COLOR + 'Invalid command format. Usage: find <word/phrase>' + END_COLOR)
            return
        query = ' '.join(command.split(' ')[1:])
        find_pages(query, index)
        return

    if command == 'exit':
        print(BLUE_COLOR + 'Exiting the search tool...' + END_COLOR)
        print('Goodbye!')
        return

    print('Invalid command.')
    print(BLUE_COLOR + 'Available commands: build, load, print, find, exit' + END_COLOR)


def interactive_loop(index_path, base_url, politeness_interval):
    print(BLUE_COLOR + '**************************************************' + END_COLOR)
    print('Welcome to Web Crawler and Search Tool')
    print('Available commands: build, load, print, find, exit')
    print(BLUE_COLOR + '**************************************************' + END_COLOR)

    while True:
        command = input(YELLOW_COLOR + 'Enter a command: ' + END_COLOR)
        handle_command(command, index_path, base_url, politeness_interval)
        if command == 'exit':
            break


def parse_args():
    parser = argparse.ArgumentParser(description='Web crawler and inverted-index search tool.')

    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument('--index-file', default=DEFAULT_INDEX_FILE, help='Path to the inverted index JSON file.')
    common_args.add_argument('--base-url', default=DEFAULT_BASE_URL, help='Website root to crawl.')
    common_args.add_argument(
        '--politeness-interval',
        type=float,
        default=DEFAULT_POLITENESS_INTERVAL,
        help='Seconds to wait between requests when crawling.',
    )

    subparsers = parser.add_subparsers(dest='command')
    subparsers.add_parser('interactive', parents=[common_args], help='Start the interactive shell.')
    subparsers.add_parser('build', parents=[common_args], help='Crawl the site and rebuild the inverted index.')
    subparsers.add_parser('load', parents=[common_args], help='Load the index file and validate it can be read.')

    print_parser = subparsers.add_parser('print', parents=[common_args], help='Print index entries for a single word.')
    print_parser.add_argument('word', help='Word to look up in the index.')

    find_parser = subparsers.add_parser('find', parents=[common_args], help='Search the loaded index for a word or phrase.')
    find_parser.add_argument('query', nargs='+', help='Word or phrase to search for.')

    web_parser = subparsers.add_parser('web', parents=[common_args], help='Start the local web UI.')
    web_parser.add_argument('--host', default=DEFAULT_WEB_HOST, help='Host for the web UI server.')
    web_parser.add_argument('--port', type=int, default=DEFAULT_WEB_PORT, help='Port for the web UI server.')

    return parser.parse_args()


def main():
    args = parse_args()
    command = args.command or 'interactive'

    try:
        if command == 'interactive':
            interactive_loop(args.index_file, args.base_url, args.politeness_interval)
        elif command == 'build':
            handle_command('build', args.index_file, args.base_url, args.politeness_interval)
        elif command == 'load':
            handle_command('load', args.index_file, args.base_url, args.politeness_interval)
        elif command == 'print':
            handle_command(f"print {args.word}", args.index_file, args.base_url, args.politeness_interval)
        elif command == 'find':
            handle_command(
                f"find {' '.join(args.query)}",
                args.index_file,
                args.base_url,
                args.politeness_interval,
            )
        elif command == 'web':
            run_web_ui(args.index_file, args.host, args.port)
    except FileNotFoundError as error:
        print(RED_COLOR + str(error) + END_COLOR)
