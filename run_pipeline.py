#!/usr/bin/env python3
"""
一键流水线 — 同步数据 → AI打标 → 索引同步 → 生成报告。

用法:
  python run_pipeline.py              # 运行完整流水线
  python run_pipeline.py --skip-report # 跳过报告生成
  python run_pipeline.py --classify-limit 50  # 仅打标50条（测试）
"""
import sys
import subprocess
import argparse
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"


def run_step(name: str, args: list) -> bool:
    print(f"\n{'='*60}")
    print(f"  [{name}]")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / args[0])] + args[1:],
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        print(f"  [{name}] 失败 (exit code: {result.returncode})")
        return False
    print(f"  [{name}] 完成")
    return True


def main():
    parser = argparse.ArgumentParser(description="新闻分析一键流水线")
    parser.add_argument("--skip-sync", action="store_true", help="跳过数据同步")
    parser.add_argument("--skip-classify", action="store_true", help="跳过AI打标")
    parser.add_argument("--skip-report", action="store_true", help="跳过报告生成")
    parser.add_argument("--classify-limit", type=int, default=0, help="AI打标数量限制")
    parser.add_argument("--config-only", action="store_true", help="仅校验配置")
    args = parser.parse_args()

    # 1. 配置校验
    if not run_step("配置校验", ["config_validate.py"]):
        return

    if args.config_only:
        return

    # 2. 数据同步
    if not args.skip_sync:
        if not run_step("数据同步", ["sync_news.py"]):
            print("警告: 数据同步失败，继续执行后续步骤")

    # 3. AI 打标
    if not args.skip_classify:
        classify_args = ["classify.py"]
        if args.classify_limit > 0:
            classify_args.extend(["--limit", str(args.classify_limit)])
        if not run_step("AI 打标", classify_args):
            print("警告: AI打标出现错误")

    # 4. 索引同步
    run_step("索引同步", ["index_sync.py"])

    # 5. 报告生成
    if not args.skip_report and not args.classify_limit:
        run_step("生成周报", ["gen_weekly.py"])
        run_step("生成月报", ["gen_monthly.py"])

    print(f"\n{'='*60}")
    print("  流水线完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
