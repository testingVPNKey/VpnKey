import json
import urllib.request
import urllib.parse
import base64
import re
from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent

SOURCES_FILE = BASE_DIR / "sources.json"
OUTPUT_FILE = BASE_DIR / "subscription.txt"
REPORT_FILE = BASE_DIR / "generation_report.json"


# Протоколы, которые считаем конфигурациями
SUPPORTED_PREFIXES = (
    "vless://",
    "vmess://",
    "trojan://",
    "ss://",
    "ssconf://",
    "hysteria://",
    "hysteria2://",
    "tuic://",
    "socks://",
    "http://",
    "https://",
)


def download(url):
    """Загрузка содержимого подписки."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()

    return data


def decode_subscription(data):
    """
    Пытается определить обычный текст или Base64-подписку.
    Возвращает список строк.
    """

    text = data.decode("utf-8", errors="ignore")

    # Сначала проверяем обычный текст.
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if any(
        line.lower().startswith(SUPPORTED_PREFIXES)
        for line in lines
    ):
        return lines

    # Иногда подписки приходят одной Base64-строкой.
    compact = re.sub(r"\s+", "", text)

    try:
        # Добавляем недостающий padding.
        padding = "=" * (-len(compact) % 4)

        decoded = base64.b64decode(
            compact + padding,
            validate=False
        )

        decoded_text = decoded.decode(
            "utf-8",
            errors="ignore"
        )

        decoded_lines = [
            line.strip()
            for line in decoded_text.splitlines()
            if line.strip()
        ]

        if any(
            line.lower().startswith(SUPPORTED_PREFIXES)
            for line in decoded_lines
        ):
            return decoded_lines

    except Exception:
        pass

    return lines


def has_name(config):
    """
    Проверяет, есть ли у конфигурации название после #.
    """

    try:
        fragment = urllib.parse.urlsplit(config).fragment

        if fragment.strip():
            return True
    except Exception:
        pass

    # Для некоторых нестандартных URI
    if "#" in config:
        name = config.split("#", 1)[1].strip()

        if name:
            return True

    return False


def add_name(config, number):
    """
    Если у конфигурации нет названия,
    добавляет безопасное название.
    """

    if has_name(config):
        return config

    # Не изменяем саму конфигурацию,
    # только добавляем fragment с названием.
    return f"{config}#Сервер {number}"


def load_sources():
    """Читает sources.json."""

    with open(
        SOURCES_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    if isinstance(data, dict):
        # Поддержка формата:
        # {"sources": [...]}
        sources = data.get("sources", [])

    elif isinstance(data, list):
        sources = data

    else:
        raise ValueError(
            "sources.json должен содержать список источников"
        )

    return sources


def main():

    started = datetime.now(timezone.utc)

    sources = load_sources()

    all_configs = []
    report_sources = []

    server_number = 1

    for source_index, source in enumerate(
        sources,
        start=1
    ):

        name = source.get(
            "name",
            f"VPN {source_index}"
        )

        url = source.get("url")

        status = {
            "name": name,
            "url": url,
            "status": "error",
            "configs": 0,
            "error": None,
        }

        if not url:
            status["error"] = "URL отсутствует"
            report_sources.append(status)
            continue

        try:
            raw_data = download(url)

            configs = decode_subscription(raw_data)

            valid_configs = []

            for config in configs:

                config = config.strip()

                if not config:
                    continue

                # Игнорируем мусор, который не является конфигурацией.
                if not config.lower().startswith(
                    SUPPORTED_PREFIXES
                ):
                    continue

                # Добавляем название только если его нет.
                config = add_name(
                    config,
                    server_number
                )

                valid_configs.append(config)

                all_configs.append(config)

                server_number += 1

            status["status"] = "ok"
            status["configs"] = len(valid_configs)

        except Exception as error:

            status["error"] = str(error)

        report_sources.append(status)

    # Убираем только полностью пустые строки.
    # Дубликаты НЕ удаляем специально.
    all_configs = [
        config
        for config in all_configs
        if config.strip()
    ]

    # Описание в начале подписки.
    description = [
        "VPN Key",
        "",
        "Агрегированная подписка с конфигурациями из нескольких источников.",
        "",
        "Если какая-то из подписок не работает, напишите в Telegram: @Tesler09785",
        "Мы проверим источник и при необходимости удалим его.",
        "",
        f"Конфигураций: {len(all_configs)}",
        "",
    ]

    output = (
        "\n".join(description)
        + "\n".join(all_configs)
        + "\n"
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(output)

    finished = datetime.now(timezone.utc)

    report = {
        "generated_at": finished.isoformat(),
        "duration_seconds": (
            finished - started
        ).total_seconds(),
        "sources_total": len(sources),
        "sources_success": sum(
            1
            for source in report_sources
            if source["status"] == "ok"
        ),
        "sources_failed": sum(
            1
            for source in report_sources
            if source["status"] == "error"
        ),
        "configs_total": len(all_configs),
        "duplicates_removed": 0,
        "traffic": {
            "available": False,
            "note": (
                "Трафик не выдумывается. "
                "Он показывается только если "
                "его предоставляет источник."
            )
        },
        "sources": report_sources,
    }

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Готово. Конфигураций: {len(all_configs)}"
    )


if __name__ == "__main__":
    main()
