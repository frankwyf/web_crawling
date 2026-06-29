import argparse
import os

from .benchmark import run_benchmark_suite
from .core import (
    BLUE_COLOR,
    DEFAULT_ASYNC_CONCURRENCY,
    DEFAULT_BASE_URL,
    DEFAULT_CRAWL_MODE,
    DEFAULT_CRAWL_REPORT_FILE,
    DEFAULT_INDEX_FILE,
    DEFAULT_POLITENESS_INTERVAL,
    DEFAULT_WEB_HOST,
    DEFAULT_WEB_PORT,
    END_COLOR,
    RED_COLOR,
    YELLOW_COLOR,
    build_index,
    crawl_website_by_mode,
    ensure_index_loaded,
    find_pages,
    generate_crawl_report,
    get_last_crawl_stats,
    index,
    print_index,
)
from .webui import run_web_ui


def _print_crawl_stats(crawl_stats):
    if not crawl_stats:
        return
    print(BLUE_COLOR + 'Crawl Summary' + END_COLOR)
    print(f"  Base URL: {crawl_stats['base_url']}")
    print(f"  Pages Crawled: {crawl_stats['pages_crawled']}")
    print(f"  Failed Pages: {crawl_stats['pages_failed']}")
    print(f"  Unique Tokens: {crawl_stats['unique_tokens']}")
    print(f"  Duration (s): {crawl_stats['duration_seconds']}")


def _print_benchmark_summary(summary):
    metrics = summary.get('metrics', {})
    print(BLUE_COLOR + 'Benchmark Summary' + END_COLOR)
    print(f"  Operations: {metrics.get('operations', 0)}")
    print(f"  Avg latency (ms): {metrics.get('avg_ms', 0)}")
    print(f"  P95 latency (ms): {metrics.get('p95_ms', 0)}")
    print(f"  Throughput (qps): {metrics.get('qps', 0)}")
    print(f"  Non-empty result rate: {metrics.get('non_empty_rate', 0)}%")
    if summary.get('regression_detected'):
        print(RED_COLOR + '  Regression: detected' + END_COLOR)
    else:
        print(BLUE_COLOR + '  Regression: none' + END_COLOR)


def handle_command(
    command,
    index_path,
    base_url,
    politeness_interval,
    max_pages=150,
    report_file=DEFAULT_CRAWL_REPORT_FILE,
    crawl_mode=DEFAULT_CRAWL_MODE,
    async_concurrency=DEFAULT_ASYNC_CONCURRENCY,
):
    if command == 'build':
        pages_content, urls, num_links = crawl_website_by_mode(
            base_url,
            politeness_interval,
            max_pages=max_pages,
            crawl_mode=crawl_mode,
            concurrency=async_concurrency,
        )
        index_data = build_index(pages_content, index_path, urls, num_links)
        crawl_stats = get_last_crawl_stats()
        _print_crawl_stats(crawl_stats)
        generate_crawl_report(report_file, pages_content, urls, num_links, index_data, crawl_stats)
        print(BLUE_COLOR + f'Crawl report saved: {report_file}' + END_COLOR)
        if os.path.exists(index_path):
            print(BLUE_COLOR + 'Inverted index built and saved successfully.' + END_COLOR)
        else:
            print(RED_COLOR + 'Failed to build the index.' + END_COLOR)
        return

    if command == 'benchmark':
        summary = run_benchmark_suite(
            index_path=index_path,
            history_file=report_file,
            runs=max(1, max_pages),
            fail_on_regression=False,
        )
        _print_benchmark_summary(summary)
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


def interactive_loop(index_path, base_url, politeness_interval, max_pages, report_file, crawl_mode, async_concurrency):
    print(BLUE_COLOR + '**************************************************' + END_COLOR)
    print('Welcome to Web Crawler and Search Tool')
    print('Available commands: build, load, print, find, exit')
    print(BLUE_COLOR + '**************************************************' + END_COLOR)

    while True:
        command = input(YELLOW_COLOR + 'Enter a command: ' + END_COLOR)
        handle_command(
            command,
            index_path,
            base_url,
            politeness_interval,
            max_pages=max_pages,
            report_file=report_file,
            crawl_mode=crawl_mode,
            async_concurrency=async_concurrency,
        )
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
    common_args.add_argument('--max-pages', type=int, default=150, help='Maximum number of pages to crawl.')
    common_args.add_argument(
        '--crawl-mode',
        choices=['sync', 'async'],
        default=DEFAULT_CRAWL_MODE,
        help='Crawl execution mode. async uses concurrent HTTP requests.',
    )
    common_args.add_argument(
        '--async-concurrency',
        type=int,
        default=DEFAULT_ASYNC_CONCURRENCY,
        help='Parallel request count for async crawl mode.',
    )
    common_args.add_argument(
        '--report-file',
        default=DEFAULT_CRAWL_REPORT_FILE,
        help='Path to JSON crawl report generated by build command.',
    )

    benchmark_args = argparse.ArgumentParser(add_help=False)
    benchmark_args.add_argument('--index-file', default=DEFAULT_INDEX_FILE, help='Path to the inverted index JSON file.')
    benchmark_args.add_argument('--history-file', default='logs/perf_history.jsonl', help='Path to benchmark history jsonl file.')
    benchmark_args.add_argument('--runs', type=int, default=3, help='How many rounds to replay query set.')
    benchmark_args.add_argument(
        '--fail-on-regression',
        action='store_true',
        help='Exit with non-zero status when benchmark regression is detected.',
    )
    benchmark_args.add_argument(
        '--query',
        action='append',
        default=[],
        help='Additional query to include in benchmark set. Repeatable.',
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

    subparsers.add_parser('benchmark', parents=[benchmark_args], help='Run search performance benchmark suite.')

    return parser.parse_args()


def main():
    args = parse_args()
    command = args.command or 'interactive'

    try:
        if command == 'interactive':
            interactive_loop(
                args.index_file,
                args.base_url,
                args.politeness_interval,
                args.max_pages,
                args.report_file,
                args.crawl_mode,
                args.async_concurrency,
            )
        elif command == 'build':
            handle_command(
                'build',
                args.index_file,
                args.base_url,
                args.politeness_interval,
                max_pages=args.max_pages,
                report_file=args.report_file,
                crawl_mode=args.crawl_mode,
                async_concurrency=args.async_concurrency,
            )
        elif command == 'load':
            handle_command(
                'load',
                args.index_file,
                args.base_url,
                args.politeness_interval,
                max_pages=args.max_pages,
                report_file=args.report_file,
                crawl_mode=args.crawl_mode,
                async_concurrency=args.async_concurrency,
            )
        elif command == 'print':
            handle_command(
                f"print {args.word}",
                args.index_file,
                args.base_url,
                args.politeness_interval,
                max_pages=args.max_pages,
                report_file=args.report_file,
                crawl_mode=args.crawl_mode,
                async_concurrency=args.async_concurrency,
            )
        elif command == 'find':
            handle_command(
                f"find {' '.join(args.query)}",
                args.index_file,
                args.base_url,
                args.politeness_interval,
                max_pages=args.max_pages,
                report_file=args.report_file,
                crawl_mode=args.crawl_mode,
                async_concurrency=args.async_concurrency,
            )
        elif command == 'web':
            run_web_ui(args.index_file, args.host, args.port)
        elif command == 'benchmark':
            summary = run_benchmark_suite(
                index_path=args.index_file,
                history_file=args.history_file,
                runs=args.runs,
                queries=args.query,
                fail_on_regression=args.fail_on_regression,
            )
            _print_benchmark_summary(summary)
    except FileNotFoundError as error:
        print(RED_COLOR + str(error) + END_COLOR)
