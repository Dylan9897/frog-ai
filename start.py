#!/usr/bin/env python3
"""
Frog AI 启动脚本
从项目根目录启动 Flask 应用
"""
import os
import sys

# 获取项目根目录和 src 目录的绝对路径
root_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(root_dir, 'src')

# 将 src 目录添加到 Python 模块搜索路径
sys.path.insert(0, src_dir)

# 切换工作目录到 src
os.chdir(src_dir)

# 启动 Flask 应用
if __name__ == '__main__':
    import main

