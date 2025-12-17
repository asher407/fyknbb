import subprocess
import sys
from pathlib import Path


def main():
    """Launch Streamlit GUI when running `python src/main.py`."""

    project_root = Path(__file__).resolve().parent.parent
    app_path = project_root / "src" / "gui" / "app.py"

    if not app_path.exists():
        print(f"[错误] 找不到 Streamlit 应用: {app_path}")
        sys.exit(1)

    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]

    try:
        # 直接将当前进程交给 streamlit；用户可在 Ctrl+C 退出
        subprocess.run(cmd, cwd=project_root, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[错误] 启动 Streamlit 失败，退出码 {exc.returncode}")
        sys.exit(exc.returncode)
    except KeyboardInterrupt:
        print("已终止 Streamlit 进程")
        sys.exit(0)

if __name__ == "__main__":
    main()
