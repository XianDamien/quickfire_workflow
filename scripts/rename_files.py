#!/usr/bin/env python3
"""批量重命名转写文件和题库 JSON 文件为 R{课号}-{序号}_{中文名} 格式。

用法:
    uv run python scripts/rename_files.py           # 干运行，仅打印计划
    uv run python scripts/rename_files.py --execute  # 实际执行重命名
"""

import csv
import os
import re
import shutil
import sys
from collections import OrderedDict
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────────────────
DATA_DIR = Path("/Users/damien/Desktop/Venture/data/grammar")
TRANSCRIPT_DIR = Path("/Users/damien/Desktop/机构资料/快反录音转写")
QB_DIR = Path("/Users/damien/Desktop/Venture/quickfire_workflow/questionbank/grammar")

R1_CSV = DATA_DIR / "R1快反.csv"
R2_CSV = DATA_DIR / "R2快反.csv"
R3_CSV = DATA_DIR / "R3快反.csv"

R1_DIR = TRANSCRIPT_DIR / "R1"
R2_DIR = TRANSCRIPT_DIR / "R2"
R3_DIR = TRANSCRIPT_DIR / "R3"
GENDUO_SRC_DIR = TRANSCRIPT_DIR / "跟读配套录音"
GENDUO_DST_DIR = TRANSCRIPT_DIR / "跟读_待确认"

# ── 跟读文件列表 ─────────────────────────────────────────────────────
GENDUO_FILES_R2 = [
    "R062-05_不定冠-固定搭配-跟读.txt",
    "R071-05_反身代词-大狗在家影子跟读.txt",
    "R098-01_adj.从句-跟读1.txt",
    "R098-02_adj.从句-跟读2.txt",
    "R099-01_n.从句-跟读.txt",
]
GENDUO_FILES_EXTRA = [
    "R068-D2 D3 D4 D5 D6跟读配套录音.txt",
    "R069-D3 D4跟读配套录音.txt",
]

# ── R1 txt 文件名 → CSV 名称的特殊映射 ───────────────────────────────
# txt 文件名（不含 .txt） → CSV 中的对应名称
TXT_TO_CSV_OVERRIDES = {
    "R011-加not后的缩写+will be": "R011-m.加not后的缩写+will be",
    "R024-5w基础知识": "R024-5W基础知识",
    "R025-5w进阶知识点": "R025-5W-进阶知识点",
    "R029-at(地点)": "R029-at（地点）",
    "R029-in(地点)": "R029-in（地点）",
    "R029-on(地点)": "R029-on（地点）",
    "R035-重要五介词—英翻中": "R035-重要五介词-英翻中",
    "R037-频率副词-中文1": "R037-频率副词--中文1",
    "R037-频率副词-中文2": "R037-频率副词--中文2",
    "R037-频率副词-英文1": "R037-频率副词--英文1",
    "R037-频率副词-英文2": "R037-频率副词--英文2",
    "R041-将来时间标志-中翻英2": "R041-将来简单时间标志-中翻英2",
    "R045-V.变cp.的规则": "R045-v.变cp.的规则",
}

# 非标准文件名修正（缺少横杠或课号位数不对）
TXT_NORMALIZATION = {
    "R037时态英文": "R037-时态英文",
    "R041将来简单时间标志-中翻英1": "R041-将来简单时间标志-中翻英1",
    "R22-定语状语综合练习": "R022-定语状语综合练习",
}

# R022-定语状语综合练习.txt 和 R22-定语状语综合练习.txt 是重复文件，
# R22 版本通过 TXT_NORMALIZATION 映射到 CSV 条目，R022 版本应跳过
TXT_DUPLICATES = {"R022-定语状语综合练习"}

# txt-only 文件（不在 CSV 中），需要插入到正确位置
TXT_ONLY_INSERTS = {
    # csv_name_after: txt_name_to_insert
    # R013-判断可数不可数3 应插入到 判断可数不可数2 和 判断可数不可数4 之间
    "R013-判断可数不可数2": "R013-判断可数不可数3",
}

# CSV 中非 R-开头的条目（应跳过）
NON_R_ENTRIES = {
    "只能用于第2课/第3课",
    "学了bev.就不能用这个快反了",
    "Tati",
}


def parse_csv(csv_path: Path) -> list[str]:
    """解析 CSV，返回有序的条目名称列表（去除非 R-开头的条目）。"""
    entries = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # 跳过 header
        for row in reader:
            if row and row[0].strip():
                name = row[0].strip()
                if name not in NON_R_ENTRIES:
                    entries.append(name)
    return entries


def extract_ke_hao(name: str) -> str:
    """从名称中提取课号，如 R001-SVO → R001，R22-xxx → R022。"""
    m = re.match(r"R(\d+)", name)
    if m:
        return f"R{int(m.group(1)):03d}"
    return ""


def extract_description(name: str) -> str:
    """从名称中提取描述部分（第一个横杠之后的内容）。"""
    m = re.match(r"R\d+-(.+)", name)
    if m:
        return m.group(1)
    # 处理没有横杠的情况（如 Tati）
    return name


def build_r1_mapping() -> list[tuple[str, str]]:
    """构建 R1 转写文件的 old_name → new_name 映射。

    返回 [(old_filename, new_filename), ...] 列表。
    """
    csv_entries = parse_csv(R1_CSV)

    # 获取实际 txt 文件列表
    txt_files = {f[:-4] for f in os.listdir(R1_DIR) if f.endswith(".txt")}

    # 正规化 txt 文件名
    txt_normalized = {}  # normalized_name → original_txt_name
    for txt_name in txt_files:
        if txt_name in TXT_DUPLICATES:
            continue  # 跳过重复文件
        if txt_name in TXT_NORMALIZATION:
            normalized = TXT_NORMALIZATION[txt_name]
        else:
            normalized = txt_name
        txt_normalized[normalized] = txt_name

    # 构建 CSV 名称 → txt 名称 的映射
    csv_to_txt = {}
    # 反向映射：txt 覆盖
    txt_override_reverse = {v: k for k, v in TXT_TO_CSV_OVERRIDES.items()}

    for csv_name in csv_entries:
        # 检查是否有 txt 覆盖映射
        if csv_name in txt_override_reverse:
            override_txt = txt_override_reverse[csv_name]
            # 检查正规化名称中是否有
            if override_txt in txt_normalized:
                csv_to_txt[csv_name] = txt_normalized[override_txt]
                continue

        # 直接匹配
        if csv_name in txt_normalized:
            csv_to_txt[csv_name] = txt_normalized[csv_name]
            continue

        # 特殊: R004-am, is, are怎么选 → txt: R004-am,is,are怎么选
        if csv_name == "R004-am, is, are怎么选":
            txt_candidate = "R004-am,is,are怎么选"
            if txt_candidate in txt_normalized:
                csv_to_txt[csv_name] = txt_normalized[txt_candidate]
                continue

        # 没有找到对应 txt 文件（如 R038-过去式跟读-Roger 仅在 CSV/JSON 中）
        csv_to_txt[csv_name] = None

    # 按课号分组，保持 CSV 顺序
    ke_groups: OrderedDict[str, list[str]] = OrderedDict()
    for csv_name in csv_entries:
        kh = extract_ke_hao(csv_name)
        if kh not in ke_groups:
            ke_groups[kh] = []
        ke_groups[kh].append(csv_name)

    # 插入 txt-only 文件
    for after_csv_name, insert_name in TXT_ONLY_INSERTS.items():
        kh = extract_ke_hao(after_csv_name)
        if kh in ke_groups:
            group = ke_groups[kh]
            try:
                idx = group.index(after_csv_name)
                group.insert(idx + 1, insert_name)
                # 这个插入的名称也需要映射到 txt
                if insert_name in txt_normalized:
                    csv_to_txt[insert_name] = txt_normalized[insert_name]
                else:
                    csv_to_txt[insert_name] = insert_name  # 名称一致
            except ValueError:
                print(f"  警告: 未找到插入参考 {after_csv_name}")

    # 生成重命名映射
    renames = []
    for kh, group in ke_groups.items():
        for seq_idx, csv_name in enumerate(group, 1):
            desc = extract_description(csv_name)
            new_name = f"{kh}-{seq_idx:02d}_{desc}.txt"
            txt_name = csv_to_txt.get(csv_name)
            if txt_name is not None:
                old_filename = f"{txt_name}.txt"
                if old_filename != new_name:
                    renames.append((old_filename, new_name))

    return renames


def build_r2_fixes() -> list[tuple[str, str, list[tuple[str, str]]]]:
    """构建 R2 未匹配文件的重命名计划。

    返回 [(old_filename, new_filename, [(cascade_old, cascade_new), ...]), ...]
    """
    renames = []
    existing_files = sorted(os.listdir(R2_DIR))

    # 1. R079: 插入替换3和替换4，需要级联重命名
    r079_files = sorted([f for f in existing_files if f.startswith("R079-")])
    r079_numbered = {}  # seq_num → filename
    r079_unnumbered = []
    for f in r079_files:
        m = re.match(r"R079-(\d{2})_(.+)\.txt", f)
        if m:
            r079_numbered[int(m.group(1))] = f
        else:
            r079_unnumbered.append(f)

    # 当前状态: 01=将军小兵, 02=5w的真面目, 03=替换1, 04=替换2, 05=替换5, 06=替换6, 07=替换7
    # 目标: 01=将军小兵, 02=5w的真面目, 03=替换1, 04=替换2, 05=替换3, 06=替换4, 07=替换5, 08=替换6, 09=替换7
    # 需要: 先将 05→07, 06→08, 07→09（从大到小避免冲突），然后插入 替换3→05, 替换4→06
    cascade = []
    # 从大到小重命名已有的
    for old_seq in sorted([5, 6, 7], reverse=True):
        if old_seq in r079_numbered:
            old_f = r079_numbered[old_seq]
            desc = re.match(r"R079-\d{2}_(.+)", old_f).group(1)
            new_seq = old_seq + 2
            new_f = f"R079-{new_seq:02d}_{desc}"
            cascade.append((old_f, new_f))

    # 插入新文件
    cascade.append(("R079-划线部分替换3.txt", "R079-05_划线部分替换3.txt"))
    cascade.append(("R079-划线部分替换4.txt", "R079-06_划线部分替换4.txt"))
    if cascade:
        renames.append(("R079-cascade", None, cascade))

    # 2. R082: 新课号，只有一个文件
    renames.append(("R082-情态-说中文1.txt", "R082-01_情态-说中文1.txt", []))

    # 3. R092: 追加到末尾 → R092-06
    renames.append(("R092-XX_时间标志对应的时态6.txt", "R092-06_时间标志对应的时态6.txt", []))

    return renames


def build_r1_full_mapping() -> dict[str, tuple[str, str]]:
    """构建 R1 完整的 CSV 名称 → (课号, 序号, 描述) 映射，用于 JSON 重命名。

    返回 {csv_name: (ke_hao, seq_str, description), ...}
    """
    csv_entries = parse_csv(R1_CSV)

    # 按课号分组
    ke_groups: OrderedDict[str, list[str]] = OrderedDict()
    for csv_name in csv_entries:
        kh = extract_ke_hao(csv_name)
        if kh not in ke_groups:
            ke_groups[kh] = []
        ke_groups[kh].append(csv_name)

    # 插入 txt-only 文件
    for after_csv_name, insert_name in TXT_ONLY_INSERTS.items():
        kh = extract_ke_hao(after_csv_name)
        if kh in ke_groups:
            group = ke_groups[kh]
            try:
                idx = group.index(after_csv_name)
                group.insert(idx + 1, insert_name)
            except ValueError:
                pass

    # 生成映射
    mapping = {}
    for kh, group in ke_groups.items():
        for seq_idx, name in enumerate(group, 1):
            desc = extract_description(name)
            mapping[name] = (kh, f"{seq_idx:02d}", desc)
    return mapping


def build_r2_full_mapping() -> dict[str, tuple[str, str, str]]:
    """从已重命名的 R2 文件中提取映射，并加入修正后的条目。

    返回 {csv_name: (ke_hao, seq_str, description), ...}
    """
    csv_entries = parse_csv(R2_CSV)
    existing_files = sorted(os.listdir(R2_DIR))

    # 从已重命名文件提取映射: R0XX-0Y_desc.txt
    numbered_by_kh: dict[str, dict[int, str]] = {}  # ke_hao → {seq: desc}
    for f in existing_files:
        m = re.match(r"(R\d{3})-(\d{2})_(.+)\.txt", f)
        if m:
            kh, seq, desc = m.group(1), int(m.group(2)), m.group(3)
            if kh not in numbered_by_kh:
                numbered_by_kh[kh] = {}
            numbered_by_kh[kh][seq] = desc

    # 按课号分组 CSV 条目
    ke_groups: OrderedDict[str, list[str]] = OrderedDict()
    for csv_name in csv_entries:
        kh = extract_ke_hao(csv_name)
        if kh not in ke_groups:
            ke_groups[kh] = []
        ke_groups[kh].append(csv_name)

    # 对已命名的课号，序号已定
    mapping = {}
    for kh, group in ke_groups.items():
        if kh in numbered_by_kh:
            # 已经有编号的文件，按 CSV 顺序分配序号
            for seq_idx, csv_name in enumerate(group, 1):
                desc = extract_description(csv_name)
                mapping[csv_name] = (kh, f"{seq_idx:02d}", desc)

    # R079: 插入替换3和替换4后的完整映射
    # CSV 有: 将军小兵, 5w的真面目, 替换1, 替换2, 替换5, 替换6, 替换7
    # 实际需要: 将军小兵(01), 5w的真面目(02), 替换1(03), 替换2(04), 替换3(05), 替换4(06), 替换5(07), 替换6(08), 替换7(09)
    if "R079" in ke_groups:
        r079_csv = ke_groups["R079"]
        # 在替换2后面插入替换3和替换4
        new_r079 = []
        for name in r079_csv:
            new_r079.append(name)
            if name == "R079-划线部分替换2":
                new_r079.append("R079-划线部分替换3")
                new_r079.append("R079-划线部分替换4")
        for seq_idx, name in enumerate(new_r079, 1):
            desc = extract_description(name)
            mapping[name] = ("R079", f"{seq_idx:02d}", desc)

    # R082: 新课号
    mapping["R082-情态-说中文1"] = ("R082", "01", "情态-说中文1")

    # R092: 追加时间标志对应的时态6
    mapping["R092-时间标志对应的时态6"] = ("R092", "06", "时间标志对应的时态6")

    return mapping


def build_r3_full_mapping() -> dict[str, tuple[str, str, str]]:
    """从已重命名的 R3 文件中提取映射。"""
    csv_entries = parse_csv(R3_CSV)

    ke_groups: OrderedDict[str, list[str]] = OrderedDict()
    for csv_name in csv_entries:
        kh = extract_ke_hao(csv_name)
        if kh not in ke_groups:
            ke_groups[kh] = []
        ke_groups[kh].append(csv_name)

    mapping = {}
    for kh, group in ke_groups.items():
        for seq_idx, csv_name in enumerate(group, 1):
            desc = extract_description(csv_name)
            mapping[csv_name] = (kh, f"{seq_idx:02d}", desc)
    return mapping


def csv_name_to_json_name(csv_name: str) -> str:
    """将 CSV 名称转换为 JSON 文件名格式（空格→横杠）。"""
    return csv_name.replace(" ", "-") + ".json"


def build_json_mapping() -> list[tuple[str, str]]:
    """构建 JSON 文件的重命名映射。"""
    # 合并所有 CSV 映射
    r1_map = build_r1_full_mapping()
    r2_map = build_r2_full_mapping()
    r3_map = build_r3_full_mapping()

    all_map = {}
    all_map.update(r1_map)
    all_map.update(r2_map)
    all_map.update(r3_map)

    # 获取实际 JSON 文件列表
    json_files = {f for f in os.listdir(QB_DIR) if f.endswith(".json")}

    # 非 R- 开头的文件保持不变
    non_r_files = {"Tati.json", "学了bev.就不能用这个快反了.json", "只能用于第2课-第3课.json"}

    renames = []
    matched_jsons = set()

    for csv_name, (kh, seq, desc) in all_map.items():
        new_json = f"{kh}-{seq}_{desc}.json"

        # 尝试多种匹配策略找到对应的 JSON 文件
        json_name = _find_json_for_csv(csv_name, json_files - matched_jsons)
        if json_name:
            matched_jsons.add(json_name)
            if json_name != new_json:
                renames.append((json_name, new_json))

    # 报告未匹配的 JSON 文件
    unmatched = json_files - matched_jsons - non_r_files
    if unmatched:
        print(f"\n  未匹配的 JSON 文件 ({len(unmatched)} 个):")
        for f in sorted(unmatched):
            print(f"    {f}")

    return renames


def _find_json_for_csv(csv_name: str, available_jsons: set[str]) -> str | None:
    """尝试找到与 CSV 名称对应的 JSON 文件。"""
    # 策略1: 直接匹配（空格→横杠）
    candidate = csv_name.replace(" ", "-") + ".json"
    if candidate in available_jsons:
        return candidate

    # 策略2: 原样
    candidate = csv_name + ".json"
    if candidate in available_jsons:
        return candidate

    # 策略3: R004-am, is, are怎么选 → R004-am,-is,-are怎么选.json
    if csv_name == "R004-am, is, are怎么选":
        candidate = "R004-am,-is,-are怎么选.json"
        if candidate in available_jsons:
            return candidate

    # 策略4: CSV 名称中 "5W" vs "5w" (大小写)
    if "5W" in csv_name:
        alt = csv_name.replace("5W", "5w").replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt
    if "5w" in csv_name:
        alt = csv_name.replace("5w", "5W").replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt

    # 策略5: 空格变横杠 + 特殊字符处理
    # 有些 JSON 文件名中空格被替换为横杠，但不是所有空格
    # 尝试不同的空格/横杠组合
    base = csv_name
    # 将所有空格替换为横杠
    alt = base.replace(" ", "-") + ".json"
    if alt in available_jsons:
        return alt

    # 策略6: 半角括号 → 全角括号
    if "(" in csv_name or ")" in csv_name:
        alt = csv_name.replace("(", "（").replace(")", "）").replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt

    # 策略7: 全角括号 → 半角括号
    if "（" in csv_name or "）" in csv_name:
        alt = csv_name.replace("（", "(").replace("）", ")").replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt

    # 策略8: 特殊 - R029 txt 使用半角括号，CSV 使用全角
    # R029-at(地点) vs R029-at（地点）
    if "R029" in csv_name:
        # 尝试半角
        alt = csv_name.replace("（", "(").replace("）", ")") + ".json"
        if alt in available_jsons:
            return alt

    # 策略9: will be → will-be
    if "will be" in csv_name:
        alt = csv_name.replace("will be", "will-be").replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt

    # 策略10: be not → be-not
    if "be not" in csv_name:
        alt = csv_name.replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt

    # 策略11: 频率副词中的双横杠
    if "频率副词" in csv_name:
        alt = csv_name.replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt

    # 策略12: R032 空格问题 "高低上下） 英翻中"
    if "高低上下" in csv_name and "英翻中" in csv_name:
        # 尝试 R032-介词（高低上下）-英翻中.json
        alt = csv_name.replace("） ", "）-").replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt

    # 策略13: R013-判断可数不可数3 (txt-only, no JSON)
    if csv_name == "R013-判断可数不可数3":
        return None  # 这是 txt-only 条目，没有对应 JSON

    # 策略14: "to do" → "to-do", "doing " → "doing-"
    if "to do" in csv_name or "doing" in csv_name:
        alt = csv_name.replace(" ", "-") + ".json"
        if alt in available_jsons:
            return alt

    # 策略15: "Let's &let us" → "Let's-&let-us"
    alt = csv_name.replace(" ", "-") + ".json"
    if alt in available_jsons:
        return alt

    return None


def step1_copy_genduo(execute: bool) -> tuple[int, int, int]:
    """Step 1: 创建跟读待确认文件夹并复制跟读文件。"""
    print("=" * 70)
    print("Step 1: 创建跟读待确认文件夹并复制跟读文件")
    print("=" * 70)

    copied = 0
    skipped = 0
    errors = 0

    if execute:
        GENDUO_DST_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  创建目录: {GENDUO_DST_DIR}")
    else:
        print(f"  [DRY-RUN] 创建目录: {GENDUO_DST_DIR}")

    # 从 R2 复制跟读文件
    for fname in GENDUO_FILES_R2:
        src = R2_DIR / fname
        dst = GENDUO_DST_DIR / fname
        if not src.exists():
            print(f"  错误: 源文件不存在 {src}")
            errors += 1
            continue
        if dst.exists():
            print(f"  跳过（已存在）: {fname}")
            skipped += 1
            continue
        if execute:
            shutil.copy2(src, dst)
            print(f"  复制: {fname}")
        else:
            print(f"  [DRY-RUN] 复制: R2/{fname} → 跟读_待确认/{fname}")
        copied += 1

    # 从 跟读配套录音 复制文件
    for fname in GENDUO_FILES_EXTRA:
        src = GENDUO_SRC_DIR / fname
        dst = GENDUO_DST_DIR / fname
        if not src.exists():
            print(f"  错误: 源文件不存在 {src}")
            errors += 1
            continue
        if dst.exists():
            print(f"  跳过（已存在）: {fname}")
            skipped += 1
            continue
        if execute:
            shutil.copy2(src, dst)
            print(f"  复制: {fname}")
        else:
            print(f"  [DRY-RUN] 复制: 跟读配套录音/{fname} → 跟读_待确认/{fname}")
        copied += 1

    print(f"  小计: 复制 {copied}, 跳过 {skipped}, 错误 {errors}")
    return copied, skipped, errors


def step2_rename_r1(execute: bool) -> tuple[int, int, int]:
    """Step 2: 重命名 R1 转写文件。"""
    print("\n" + "=" * 70)
    print("Step 2: 重命名 R1 转写文件")
    print("=" * 70)

    renames = build_r1_mapping()
    renamed = 0
    skipped = 0
    errors = 0

    for old_name, new_name in renames:
        old_path = R1_DIR / old_name
        new_path = R1_DIR / new_name
        if not old_path.exists():
            # 可能已经被重命名过了
            if new_path.exists():
                skipped += 1
                continue
            print(f"  错误: 源文件不存在 {old_path}")
            errors += 1
            continue
        if new_path.exists():
            print(f"  错误: 目标文件已存在 {new_path}")
            errors += 1
            continue
        if execute:
            os.rename(old_path, new_path)
            print(f"  重命名: {old_name} → {new_name}")
        else:
            print(f"  [DRY-RUN] {old_name} → {new_name}")
        renamed += 1

    print(f"  小计: 重命名 {renamed}, 跳过 {skipped}, 错误 {errors}")
    return renamed, skipped, errors


def step3_fix_r2(execute: bool) -> tuple[int, int, int]:
    """Step 3: 处理 R2 剩余未匹配文件。"""
    print("\n" + "=" * 70)
    print("Step 3: 处理 R2 未匹配文件")
    print("=" * 70)

    fixes = build_r2_fixes()
    renamed = 0
    skipped = 0
    errors = 0

    for item in fixes:
        old_name, new_name, cascade = item

        if old_name == "R079-cascade":
            print("  R079 级联重命名:")
            for c_old, c_new in cascade:
                c_old_path = R2_DIR / c_old
                c_new_path = R2_DIR / c_new
                if not c_old_path.exists():
                    if c_new_path.exists():
                        print(f"    跳过（已完成）: {c_new}")
                        skipped += 1
                        continue
                    print(f"    错误: 源文件不存在 {c_old_path}")
                    errors += 1
                    continue
                if c_new_path.exists():
                    print(f"    错误: 目标文件已存在 {c_new_path}")
                    errors += 1
                    continue
                if execute:
                    os.rename(c_old_path, c_new_path)
                    print(f"    重命名: {c_old} → {c_new}")
                else:
                    print(f"    [DRY-RUN] {c_old} → {c_new}")
                renamed += 1
        else:
            old_path = R2_DIR / old_name
            new_path = R2_DIR / new_name
            if not old_path.exists():
                if new_path.exists():
                    print(f"  跳过（已完成）: {new_name}")
                    skipped += 1
                    continue
                print(f"  错误: 源文件不存在 {old_path}")
                errors += 1
                continue
            if new_path.exists():
                print(f"  错误: 目标文件已存在 {new_path}")
                errors += 1
                continue
            if execute:
                os.rename(old_path, new_path)
                print(f"  重命名: {old_name} → {new_name}")
            else:
                print(f"  [DRY-RUN] {old_name} → {new_name}")
            renamed += 1

    print(f"  小计: 重命名 {renamed}, 跳过 {skipped}, 错误 {errors}")
    return renamed, skipped, errors


def step4_rename_json(execute: bool) -> tuple[int, int, int]:
    """Step 4: 重命名题库 JSON 文件。"""
    print("\n" + "=" * 70)
    print("Step 4: 重命名题库 JSON 文件")
    print("=" * 70)

    renames = build_json_mapping()
    renamed = 0
    skipped = 0
    errors = 0

    for old_name, new_name in renames:
        old_path = QB_DIR / old_name
        new_path = QB_DIR / new_name
        if not old_path.exists():
            if new_path.exists():
                skipped += 1
                continue
            print(f"  错误: 源文件不存在 {old_path}")
            errors += 1
            continue
        if new_path.exists() and old_path != new_path:
            print(f"  错误: 目标文件已存在 {new_path}")
            errors += 1
            continue
        if execute:
            os.rename(old_path, new_path)
            print(f"  重命名: {old_name} → {new_name}")
        else:
            print(f"  [DRY-RUN] {old_name} → {new_name}")
        renamed += 1

    print(f"  小计: 重命名 {renamed}, 跳过 {skipped}, 错误 {errors}")
    return renamed, skipped, errors


def main():
    execute = "--execute" in sys.argv

    if execute:
        print(">>> 执行模式：将实际重命名文件 <<<")
    else:
        print(">>> 干运行模式：仅显示计划，不做任何更改 <<<")
        print(">>> 添加 --execute 参数以实际执行 <<<")
    print()

    total_processed = 0
    total_renamed = 0
    total_skipped = 0
    total_errors = 0

    # Step 1
    c, s, e = step1_copy_genduo(execute)
    total_processed += c + s + e
    total_renamed += c
    total_skipped += s
    total_errors += e

    # Step 2
    c, s, e = step2_rename_r1(execute)
    total_processed += c + s + e
    total_renamed += c
    total_skipped += s
    total_errors += e

    # Step 3
    c, s, e = step3_fix_r2(execute)
    total_processed += c + s + e
    total_renamed += c
    total_skipped += s
    total_errors += e

    # Step 4
    c, s, e = step4_rename_json(execute)
    total_processed += c + s + e
    total_renamed += c
    total_skipped += s
    total_errors += e

    # 汇总
    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    print(f"  总计处理: {total_processed}")
    print(f"  重命名/复制: {total_renamed}")
    print(f"  跳过: {total_skipped}")
    print(f"  错误: {total_errors}")

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
