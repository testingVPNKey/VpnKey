import base64
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCES_FILE = ROOT / "sources.json"
OUTPUT_FILE = ROOT / "subscription.txt"
REPORT_FILE = ROOT / "generation_report.json"

TIMEOUT = 20

PREFIXES = (
    "vmess://",
    "vless://",
    "trojan://",
    "ss://",
    "ssr://",
    "hysteria://",
    "hysteria2://",
    "tuic://",
    "socks://",
    "socks5://"
)


def download(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def decode_base64(text):
    compact = re.sub(r"\s+", "", text)

    if not compact:
        return None

    try:
        padding = "=" * (-len(compact) % 4)

        decoded = base64.b64decode(
            compact + padding
        ).decode("utf-8", errors="ignore")

        if any(prefix in decoded for prefix in PREFIXES):
            return decoded

    except Exception:
        pass

    return None


def extract_nodes(data):
    text = data.decode(
        "utf-8",
        errors="ignore"
    )

    decoded = decode_base64(text)

    if decoded:
        text += "\n" + decoded

    result = []
    seen = set()

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        for token in re.split(r"\s+", line):

            if token.startswith(PREFIXES):

                if token not in seen:
                    seen.add(token)
                    result.append(token)

    return result


def main():

    config = json.loads(
        SOURCES_FILE.read_text(
            encoding="utf-8"
        )
    )

    all_nodes = []
    report = []

    for source in config["subscriptions"]:

        name = source["name"]
        url = source["url"]

        item = {
            "name": name,
            "url": url,
            "status": "unknown",
            "nodes": 0
        }

        try:

            data = download(url)
            nodes = extract_nodes(data)

            item["nodes"] = len(nodes)

            if nodes:
                item["status"] = "working"
            else:
                item["status"] = "no_nodes_found"

            all_nodes.extend(nodes)

        except Exception as error:

            item["status"] = "error"
            item["error"] = str(error)

        report.append(item)

    unique_nodes = list(
        dict.fromkeys(all_nodes)
    )

    OUTPUT_FILE.write_text(
        "\n".join(unique_nodes) +
        ("\n" if unique_nodes else ""),
        encoding="utf-8"
    )

    REPORT_FILE.write_text(
        json.dumps(
            {
                "description": config["description"],
                "sources": report,
                "total_nodes": len(unique_nodes)
            },
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"Готово. Серверов собрано: {len(unique_nodes)}"
    )


if __name__ == "__main__":
    main()