"""실행: python -m src.util 소득세법"""
import argparse
import sys

from .law_api import DEFAULT_API_KEY, fetch_and_save


def main() -> None:
    parser = argparse.ArgumentParser(description="law.go.kr API로 법령 조문 저장")
    parser.add_argument("query", help="검색할 법령명 (예: 소득세법)")
    parser.add_argument("-n", "--limit", type=int, default=1, help="가져올 법령 수")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="Open API 사용자 ID (OC)")
    args = parser.parse_args()

    results = fetch_and_save(args.query, limit=args.limit, api_key=args.api_key)
    if not results:
        print("검색 결과가 없습니다.", file=sys.stderr)
        sys.exit(1)

    for item in results:
        meta = item["meta"]
        print(f"\n[{meta['법령명한글']}] ID={meta['법령일련번호']} 조문 {item['article_count']}개")
        for kind, path in item["paths"].items():
            print(f"  - {kind}: {path}")
        if item["sample"]:
            print(f"  예시: {item['sample']['조문표시']}")
            print(f"        {item['sample']['조문내용'][:120]}...")

    print("\n완료")


if __name__ == "__main__":
    main()
