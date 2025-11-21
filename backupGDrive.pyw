import os
import shutil
import stat
import time
import sys
from datetime import datetime
from pathlib import Path

# ================== 配置区域 ==================

TASKS = [
    (r"C:\Users\*\OneDrive\文档", "OneDrive_Docs", False),
    (r"C:\Users\*\Documents", "Local_Documents", True)
]

DEST_ROOT = r"G:\Arch"
LOG_DIR = r"G:\Arch\Log"
SEEN_FILES_FINGERPRINTS = set()

# ================== 强健的日志系统 (修复EXE报错) ==================

class DualLogger:
    def __init__(self):
        self.terminal = sys.stdout
        self.log_buffer = []

    def write(self, message):
        # 修复：在打包环境中，terminal 可能是 None，必须先判断
        if self.terminal is not None:
            try:
                self.terminal.write(message)
            except Exception:
                pass
        self.log_buffer.append(str(message))

    def flush(self):
        if self.terminal is not None:
            try:
                self.terminal.flush()
            except Exception:
                pass

    def save_to_file(self):
        try:
            log_path = Path(LOG_DIR)
            log_path.mkdir(parents=True, exist_ok=True)
            filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
            full_path = log_path / filename
            
            with open(full_path, "w", encoding="utf-8") as f:
                f.write("".join(self.log_buffer))
            
            if self.terminal is not None:
                self.terminal.write(f"\n[系统] 日志已保存至: {full_path}\n")
        except Exception as e:
            if self.terminal is not None:
                self.terminal.write(f"\n[警告] 日志保存失败: {e}\n")

# ================== 核心逻辑 ==================

def is_hidden(path):
    try:
        return bool(os.stat(path).st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        return False

def get_file_fingerprint(path):
    try:
        st = path.stat()
        return (path.name, st.st_size, int(st.st_mtime))
    except Exception:
        return None

def process_file(src_file, dst_file):
    """
    处理单个文件：
    包含严格的‘已存在跳过’逻辑，避免重复 I/O。
    """
    # 1. 全局指纹去重 (跨文件夹重复文件跳过)
    fingerprint = get_file_fingerprint(src_file)
    if fingerprint:
        if fingerprint in SEEN_FILES_FINGERPRINTS:
            # 如果想要日志更清爽，可以注释掉下面这行
            # print(f"[去重跳过] {src_file.name}")
            return
        SEEN_FILES_FINGERPRINTS.add(fingerprint)

    try:
        # 2. 严格的本地对比 (同名文件跳过逻辑)
        if dst_file.exists():
            src_stat = src_file.stat()
            dst_stat = dst_file.stat()

            # 判断 A: 文件大小必须完全一致
            size_match = (src_stat.st_size == dst_stat.st_size)

            # 判断 B: 修改时间
            # 逻辑：如果源文件时间 <= 目标文件时间 (允许5秒误差，应对文件系统和网络导致的差异)
            # 且 大小也一致，那就不需要复制了
            time_match = (src_stat.st_mtime <= dst_stat.st_mtime + 5)

            if size_match and time_match:
                # 文件没变，直接 return，不读取内容，不产生 I/O
                return 

        # 3. 执行复制
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"[复制] {src_file.name}")
        shutil.copy2(src_file, dst_file)
        
    except Exception as e:
        print(f"[错误] 无法复制 {src_file}: {e}")

def sync_folder_recursive(src_folder, dst_folder):
    src_folder = Path(src_folder)
    dst_folder = Path(dst_folder)

    if not src_folder.exists(): return

    for root, dirs, files in os.walk(src_folder):
        root_path = Path(root)
        rel_path = root_path.relative_to(src_folder)
        current_dst_dir = dst_folder / rel_path

        for file in files:
            process_file(root_path / file, current_dst_dir / file)

def sync_documents_special(src_root, dst_root):
    src_root = Path(src_root)
    dst_root = Path(dst_root)

    if not src_root.exists(): return

    print(f"正在扫描一级目录 (含隐藏过滤): {src_root}")

    for item in src_root.iterdir():
        if is_hidden(item):
            # 这里如果不想看大量跳过日志，可以注释掉
            # print(f"[隐藏过滤] {item.name}")
            continue
        
        if item.is_dir():
            sync_folder_recursive(item, dst_root / item.name)
        elif item.is_file():
            process_file(item, dst_root / item.name)

# ================== 主程序 ==================

def main():
    logger = DualLogger()
    sys.stdout = logger 

    # 这里的 print 在无界面模式下只会被写入日志文件
    print("=== 开始增量备份 (严格跳过模式) ===")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start_time = time.time()

    for src, subfolder, check_hidden in TASKS:
        full_dest = Path(DEST_ROOT) / subfolder
        print(f"\n>>> 正在处理: {subfolder}")
        
        if check_hidden:
            sync_documents_special(src, full_dest)
        else:
            sync_folder_recursive(src, full_dest)

    end_time = time.time()
    duration = end_time - start_time
    print(f"\n=== 备份完成，耗时 {duration:.2f} 秒 ===")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    logger.save_to_file()
    sys.stdout = logger.terminal

if __name__ == "__main__":
    main()
