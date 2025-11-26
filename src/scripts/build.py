"""
打包脚本 - 将应用打包成 exe 可执行文件
使用 PyInstaller 打包，无控制台窗口，输出到 output 文件夹
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path, PurePosixPath

# 获取项目根目录（src 的父目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "output"
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
SPEC_DIR = PROJECT_ROOT / "spec"

# 主入口文件
MAIN_ENTRY = SRC_DIR / "sandbox.py"
EXE_NAME = "sandbox"


def check_pyinstaller():
    """检查 PyInstaller 是否已安装，并尝试升级到最新版本"""
    try:
        import PyInstaller
        current_version = PyInstaller.__version__
        print(f"✓ PyInstaller 已安装 (版本: {current_version})")

        # 尝试升级到最新版本（解决兼容性问题）
        print("正在检查 PyInstaller 更新...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✓ PyInstaller 升级完成（请以实际运行版本为准）")
        except Exception as e:
            print(f"  升级失败: {e}")

        return True
    except ImportError:
        print("✗ PyInstaller 未安装")
        print("正在安装 PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✓ PyInstaller 安装成功")
            return True
        except subprocess.CalledProcessError:
            print("✗ PyInstaller 安装失败，请手动安装: pip install pyinstaller")
            return False


def clean_build_dirs():
    """清理之前的构建目录"""
    print("\n[清理] 清理之前的构建文件...")
    for dir_path in [BUILD_DIR, DIST_DIR, SPEC_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  ✓ 已删除: {dir_path}")

    # 清理 output 目录中的旧文件
    if OUTPUT_DIR.exists():
        for item in OUTPUT_DIR.iterdir():
            if item.is_file() and item.suffix == ".exe":
                item.unlink()
                print(f"  ✓ 已删除旧 exe: {item.name}")
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ 已创建输出目录: {OUTPUT_DIR}")


def build_exe():
    """使用 PyInstaller 打包 exe"""
    print("\n[打包] 开始打包 exe 文件...")

    if not MAIN_ENTRY.exists():
        print(f"✗ 错误: 找不到入口文件 {MAIN_ENTRY}")
        return False

    # 检查模板目录是否存在
    templates_dir = SRC_DIR / 'tianwa' / 'templates'
    add_data_args = []
    if templates_dir.exists():
        src_path = str(templates_dir.resolve())
        dst_path = str(PurePosixPath("tianwa", "templates"))  # 使用 POSIX 风格路径
        add_data_args = ["--add-data", f"{src_path}{os.pathsep}{dst_path}"]

    # PyInstaller 命令参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(MAIN_ENTRY),
        "--name", EXE_NAME,
        "--noconsole",  # 无控制台窗口（GUI 应用）
        "--clean",  # 清理临时文件
        "--noupx",  # 禁用 UPX 压缩（避免兼容性问题）
        "--distpath", str(DIST_DIR),  # 输出目录
        "--workpath", str(BUILD_DIR),  # 工作目录
        "--specpath", str(SPEC_DIR),  # spec 文件目录
        "--log-level=WARN",  # 减少日志输出
    ]

    # 使用单文件模式
    cmd.append("--onefile")

    # 添加数据文件
    if add_data_args:
        cmd.extend(add_data_args)

    # 收集完整包依赖（解决依赖分析问题）
    cmd.extend([
        "--collect-all", "PyQt5",
        "--collect-all", "dashscope",
        "--collect-all", "flask",
        "--collect-all", "pandas",
        "--collect-all", "openpyxl",
    ])

    # 隐藏导入（PyInstaller 可能无法自动检测的模块）
    hidden_imports = [
        "PyQt5", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
        "src", "src.database", "src.database.operate", "src.database.sql_manager",
        "src.config", "src.tianwa", "src.agents",
        "dashscope", "dashscope.Generation",
        "flask", "flask.templating",
        "pandas", "openpyxl",
        "sqlite3", "threading", "uuid", "datetime",
    ]

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # 设置工作目录为项目根目录
    try:
        print(f"  入口文件: {MAIN_ENTRY}")
        print(f"  输出目录: {OUTPUT_DIR}")
        print(f"  当前 Python: {sys.version} ({platform.architecture()[0]})")
        print(f"  执行命令: {' '.join(cmd[:5])} ...")
        print(f"  使用 --collect-all 收集完整依赖")

        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=False
        )

        print("✓ PyInstaller 打包完成")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n✗ PyInstaller 打包失败")
        print(f"  错误代码: {e.returncode}")
        print(f"\n提示: 如果遇到依赖分析错误，可以尝试:")
        print(f"  1. 升级 PyInstaller: pip install --upgrade pyinstaller")
        print(f"  2. 检查 Python 版本兼容性")
        print(f"  3. 清理 Python 缓存: find . -type d -name __pycache__ -exec rm -r {{}} +")
        return False
    except Exception as e:
        print(f"✗ 打包过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def move_exe_to_output():
    """将生成的 exe 文件移动到 output 目录"""
    print("\n[移动] 将 exe 文件移动到 output 目录...")

    exe_file = DIST_DIR / f"{EXE_NAME}.exe"
    if not exe_file.exists():
        print(f"✗ 错误: 找不到生成的 exe 文件 {exe_file}")
        return False

    output_exe = OUTPUT_DIR / f"{EXE_NAME}.exe"

    # 如果 output 目录中已存在同名文件，先删除
    if output_exe.exists():
        output_exe.unlink()

    # 移动文件
    shutil.move(str(exe_file), str(output_exe))
    print(f"✓ exe 文件已移动到: {output_exe}")
    print(f"  文件大小: {output_exe.stat().st_size / 1024 / 1024:.2f} MB")

    return True


def main():
    """主函数"""
    print("=" * 70)
    print("🐸 Frog AI - EXE 打包工具")
    print("=" * 70)

    # 1. 检查 PyInstaller
    if not check_pyinstaller():
        return 1

    # 2. 清理构建目录
    clean_build_dirs()

    # 3. 打包 exe
    if not build_exe():
        return 1

    # 4. 移动 exe 到 output 目录
    if not move_exe_to_output():
        return 1

    # 5. 清理临时文件（可选）
    print("\n[清理] 清理临时构建文件...")
    for dir_path in [BUILD_DIR, DIST_DIR, SPEC_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  ✓ 已删除: {dir_path}")

    print("\n" + "=" * 70)
    print("✓ 打包完成！")
    print(f"✓ exe 文件位置: {OUTPUT_DIR / f'{EXE_NAME}.exe'}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())



