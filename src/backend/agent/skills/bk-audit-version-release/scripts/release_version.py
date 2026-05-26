#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蓝鲸审计中心版本发布自动化脚本

用法:
    python release_version.py --version 1.19.2 \
      --changelog "[ 新增 ] 审计工具新增 API 工具" \
      --commit "feat: 审计中心-V1.19.2版本发布 --story=129850328"
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd, check=True):
    """执行 shell 命令"""
    print(f"执行命令: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"错误: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def get_current_date():
    """获取当前日期，格式：YYYYMMDD"""
    return datetime.now().strftime("%Y%m%d")


def create_branch(branch_name):
    """创建并切换到新分支"""
    print(f"\n=== 步骤 1: 创建分支 {branch_name} ===")

    # 检查当前分支
    current_branch = run_command("git branch --show-current")
    print(f"当前分支: {current_branch}")

    # 切换到 main 分支
    print("切换到 main 分支...")
    run_command("git checkout main")

    # 拉取最新代码
    print("拉取最新代码...")
    run_command("git pull origin main", check=False)

    # 创建新分支
    print(f"创建分支 {branch_name}...")
    run_command(f"git checkout -b {branch_name}")

    print(f"✓ 已创建并切换到分支 {branch_name}")


def update_release_md(version, changelog):
    """更新 release.md 文件"""
    print("\n=== 步骤 2: 更新 release.md ===")

    release_md_path = Path("release.md")
    if not release_md_path.exists():
        print("错误: release.md 文件不存在")
        sys.exit(1)

    content = release_md_path.read_text(encoding="utf-8")

    # 提取版本号（去掉 release- 前缀和 V 前缀）
    version_num = version.replace("release-", "").replace("V", "")

    # 构建新的版本日志部分
    new_section = f"## V{version_num} 版本更新日志\n\n{changelog}\n\n"

    # 在文件开头插入新版本日志
    content = new_section + content

    release_md_path.write_text(content, encoding="utf-8")
    print("✓ 已更新 release.md")


def update_readme(version):
    """更新 readme.md 和 readme_en.md"""
    print("\n=== 步骤 3: 更新 readme 文件 ===")

    version_num = version.replace("release-", "").replace("V", "")

    for readme_file in ["readme.md", "readme_en.md"]:
        readme_path = Path(readme_file)
        if not readme_path.exists():
            print(f"警告: {readme_file} 文件不存在，跳过")
            continue

        content = readme_path.read_text(encoding="utf-8")

        # 更新版本号徽章
        pattern = r'(\[!\[Release Version\]\(https://img\.shields\.io/badge/release-)[\d.]+(-brightgreen\.svg\)\])'
        replacement = rf'\1{version_num}\2'
        content = re.sub(pattern, replacement, content)

        readme_path.write_text(content, encoding="utf-8")
        print(f"✓ 已更新 {readme_file}")


def update_package_json(version):
    """更新 package.json"""
    print("\n=== 步骤 4: 更新 package.json ===")

    version_num = version.replace("release-", "").replace("V", "")
    package_json_path = Path("src/frontend/package.json")

    if not package_json_path.exists():
        print("错误: package.json 文件不存在")
        sys.exit(1)

    content = package_json_path.read_text(encoding="utf-8")

    # 更新 version 字段
    pattern = r'("version":\s*")[\d.]+(")'
    replacement = rf'\1{version_num}\2'
    content = re.sub(pattern, replacement, content)

    package_json_path.write_text(content, encoding="utf-8")
    print("✓ 已更新 package.json")


def update_version_file(version):
    """更新 VERSION 文件"""
    print("\n=== 步骤 5: 更新 VERSION 文件 ===")

    version_num = version.replace("release-", "").replace("V", "")
    version_path = Path("src/backend/VERSION")

    if not version_path.exists():
        print("错误: VERSION 文件不存在")
        sys.exit(1)

    version_path.write_text(f"V{version_num}\n", encoding="utf-8")
    print("✓ 已更新 VERSION")


def create_changelog_files(version, changelog, changelog_en, date):
    """创建版本日志文件"""
    print("\n=== 步骤 6: 创建版本日志文件 ===")

    version_num = version.replace("release-", "").replace("V", "")
    version_md_dir = Path("src/backend/version_md")

    if not version_md_dir.exists():
        print("错误: version_md 目录不存在")
        sys.exit(1)

    # 中文版本日志
    zh_cn_content = f"## V{version_num} 版本更新日志\n\n{changelog}\n"
    zh_cn_file = version_md_dir / f"V{version_num}_{date}_zh-cn.md"
    zh_cn_file.write_text(zh_cn_content, encoding="utf-8")
    print(f"✓ 已创建 {zh_cn_file.name}")

    # 英文版本日志
    if not changelog_en:
        print("⚠ 警告: 未提供英文版本日志，将使用中文内容代替")
        changelog_en = changelog

    en_content = f"## Version {version_num} Release Notes\n\n- [ NEW ] {changelog_en}\n"
    en_file = version_md_dir / f"V{version_num}_{date}_en.md"
    en_file.write_text(en_content, encoding="utf-8")
    print(f"✓ 已创建 {en_file.name}")


def commit_changes(commit_message):
    """提交更改"""
    print("\n=== 步骤 7: 提交更改 ===")

    # 添加所有更改的文件
    print("添加文件到暂存区...")
    run_command("git add -A")

    # 提交
    print(f"提交更改: {commit_message}")
    run_command(f'git commit --no-verify -m "{commit_message}"')

    print("✓ 已提交更改")


def main():
    parser = argparse.ArgumentParser(description="蓝鲸审计中心版本发布自动化脚本")
    parser.add_argument("--version", required=True, help="版本号，例如: 1.19.2 或 release-1.19.2")
    parser.add_argument("--changelog", required=True, help="中文版本日志内容")
    parser.add_argument("--changelog-en", help="英文版本日志内容 (可选)")
    parser.add_argument("--commit", required=True, help="Commit 信息")
    parser.add_argument("--date", help="日期，格式: YYYYMMDD (默认: 当前日期)")

    args = parser.parse_args()

    # 确定日期
    date = args.date if args.date else get_current_date()

    # 规范化版本号
    version = args.version
    if not version.startswith("release-"):
        branch_name = f"release-{version}"
    else:
        branch_name = version
        version = version.replace("release-", "")

    print(f"版本号: {version}")
    print(f"分支名: {branch_name}")
    print(f"日期: {date}")
    print(f"中文版本日志: {args.changelog}")
    if args.changelog_en:
        print(f"英文版本日志: {args.changelog_en}")
    print(f"Commit 信息: {args.commit}")

    # 执行步骤
    try:
        create_branch(branch_name)
        update_release_md(version, args.changelog)
        update_readme(version)
        update_package_json(version)
        update_version_file(version)
        create_changelog_files(version, args.changelog, args.changelog_en, date)
        commit_changes(args.commit)

        print("\n" + "=" * 50)
        print("✓ 版本发布流程完成！")
        print("=" * 50)
        print("\n下一步:")
        print("1. 检查更改: git status")
        print(f"2. 推送分支: git push -u origin {branch_name}")
        print("3. 创建 Pull Request")

    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
