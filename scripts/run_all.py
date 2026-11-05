"""اجرای کل مسیر: خواندن RSS، تحلیل، محاسبه‌ی رتبه.

اجرا:  python scripts/run_all.py
تست محلی:  python scripts/run_all.py --mock --allow-file
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(script, *args):
    code = subprocess.call([sys.executable, str(HERE / script), *args])
    if code != 0:
        print(f"{script} با کد {code} تمام شد.")
    return code


if __name__ == "__main__":
    mock = "--mock" in sys.argv
    allow_file = "--allow-file" in sys.argv
    feeds_args = []
    if "--feeds" in sys.argv:
        feeds_args = ["--feeds", sys.argv[sys.argv.index("--feeds") + 1]]
    fetch_code = run("fetch_news.py", *(["--allow-file"] if allow_file else []), *feeds_args)
    # اگر RSS خطا داد، باز هم خبرهای قبلی را تحلیل و رتبه‌ها را بازسازی می‌کنیم
    analyze_code = run("analyze.py", *(["--mock"] if mock else []))
    build_code = run("build_scores.py", *(["--include-mock"] if mock else []))
    sys.exit(0 if analyze_code == 0 and build_code == 0 else 1)
