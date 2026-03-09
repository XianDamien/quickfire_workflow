"""
将快反 CSV 转换为题号 JSON

输入: /Users/damien/Desktop/Venture/data/grammar/R*.csv
输出: questionbank/grammar/{section_name}.json

字段:
  card_index  — 题号（从 1 开始）
  hint        — 暂时留空
  question    — CSV 第 2 列（问题）
  answer      — CSV 第 3 列（答案）
"""

import csv
import json
import re
import sys
from pathlib import Path

CSV_FILES = [
    "/Users/damien/Desktop/Venture/data/grammar/R1快反.csv",
    "/Users/damien/Desktop/Venture/data/grammar/R2快反.csv",
    "/Users/damien/Desktop/Venture/data/grammar/R3快反.csv",
    "/Users/damien/Desktop/Venture/data/grammar/R4快反.csv",
]

OUTPUT_DIR = Path(__file__).parent.parent / "questionbank" / "grammar"


def sanitize_filename(name: str) -> str:
    """将 section 名称转换为合法文件名（保留中文，替换空格）"""
    name = name.strip()
    name = re.sub(r"\s+", "-", name)              # 空格 → 短横线
    name = re.sub(r"[/\\:*?\"<>|]", "-", name)   # 非法字符 → 短横线
    return name


def parse_csv(filepath: str) -> dict[str, list[dict]]:
    """解析 CSV，返回 {section_name: [card, ...]} 字典（保序）"""
    sections: dict[str, list[dict]] = {}
    current_section: str | None = None

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # 跳过表头行

        for row in reader:
            # 补齐到 3 列（部分行只有 2 列）
            while len(row) < 3:
                row.append("")

            section_raw, question, answer = row[0].strip(), row[1].strip(), row[2].strip()

            # 新 section 开始
            if section_raw:
                current_section = section_raw
                if current_section not in sections:
                    sections[current_section] = []

            # 无 section 上下文时跳过
            if current_section is None:
                continue

            # question 或 answer 为空则跳过（无问答配对的指令行/空白行）
            if not question or not answer:
                continue

            sections[current_section].append({
                "card_index": len(sections[current_section]) + 1,
                "hint": "",
                "question": question,
                "answer": answer,
            })

    return sections


def write_sections(sections: dict[str, list[dict]], output_dir: Path) -> list[str]:
    """写入 JSON 文件，返回生成的文件名列表"""
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []

    for section_name, cards in sections.items():
        if not cards:
            continue  # 跳过空 section

        filename = sanitize_filename(section_name) + ".json"
        out_path = output_dir / filename

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)

        written.append(filename)
        print(f"  ✓ {filename}  ({len(cards)} 题)")

    return written


def main():
    total_files = 0
    total_cards = 0

    for csv_path in CSV_FILES:
        print(f"\n处理: {Path(csv_path).name}")
        sections = parse_csv(csv_path)
        written = write_sections(sections, OUTPUT_DIR)
        file_count = len(written)
        card_count = sum(len(s) for s in sections.values())
        total_files += file_count
        total_cards += card_count
        print(f"  → {file_count} 个文件，共 {card_count} 题")

    print(f"\n完成：共生成 {total_files} 个 JSON，合计 {total_cards} 题")
    print(f"输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
