import requests
import time
from datetime import datetime
import os
import subprocess
import pandas as pd

# ==================== Git 推送配置 ====================
GITHUB_REPO = "Juineii/kickflip_km0405"        # 请替换为您的仓库名
GITHUB_BRANCH = "main"                          # 分支名（main 或 master）
# GitHub Personal Access Token 优先从环境变量 GITHUB_TOKEN 读取

# ==================== 可自定义配置 ====================
CSV_FILENAME = "DONGHWA合影.csv"          # 自定义 CSV 文件名

# 台湾地址监控配置
TAIWAN_URL = "https://www.kmonstar.com.tw/products/%E6%87%89%E5%8B%9F-260502-kickflip-the-4th-mini-album-my-first-kick-11%E6%8B%8D%E7%AB%8B%E5%BE%97%E5%90%88%E7%85%A7%E6%B4%BB%E5%8B%95-in-taipei.json"
TAIWAN_TARGET_OPTION = "동화 DONGHWA"    # 监控的选项名称 (option1)
TAIWAN_PRODUCT_NAME = "台湾地址"         # CSV 中显示的商品名

# 国际地址监控配置
INTERNATIONAL_URL = "https://kmonstar.com/api/v1/event/detail/cf2854d1-c23c-4cf1-b80b-7d363470f39a"
INTERNATIONAL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://kmonstar.org/zh/eventproductdetail/c52ecf14-69a2-4869-92e3-81d0df35123e",
    "Origin": "https://kmonstar.org",
    "Cookie": "nation=KR"
}
# 国际地址只监控一个成员（原脚本中 MEMBER_NAMES 只有一个）
INTERNATIONAL_MEMBER_NAME = "동화 DONGHWA"
INTERNATIONAL_PRODUCT_NAME = "国际地址"   # CSV 中显示的商品名


# ==================== Git 推送函数 ====================
def git_push_update():
    """
    将最新的 CSV 文件提交并推送到 GitHub
    """
    try:
        # 获取 GitHub Token（优先从环境变量读取）
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            print("⚠️ 环境变量 GITHUB_TOKEN 未设置，跳过 Git 推送")
            return

        # 构建带认证的远程仓库 URL
        remote_url = f"https://{token}@github.com/{GITHUB_REPO}.git"

        # 添加 CSV 文件到暂存区
        subprocess.run(['git', 'add', CSV_FILENAME], check=True, capture_output=True)

        # 检查是否有文件变化（避免空提交）
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True)
        if result.returncode != 0:
            # 有变化，提交
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_msg = f"自动更新数据 {timestamp}"
            subprocess.run(['git', 'commit', '-m', commit_msg], check=True, capture_output=True)

            # 推送到 GitHub（指定分支）
            subprocess.run(
                ['git', 'push', remote_url, f'HEAD:{GITHUB_BRANCH}'],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✅ 已推送到 GitHub: {commit_msg}")
        else:
            print("⏭️ CSV 文件无变化，跳过推送")

    except subprocess.CalledProcessError as e:
        print(f"❌ Git 操作失败: {e.stderr if e.stderr else e}")
    except Exception as e:
        print(f"❌ 推送过程中发生错误: {e}")


# ==================== 辅助函数 ====================
def append_to_csv(time_str: str, product_name: str, stock_change: str, single_sales: int):
    try:
        columns = ["时间", "商品名称", "库存变化", "单笔销量"]
        # 确保 single_sales 是整数
        single_sales = int(single_sales) if single_sales is not None else 0

        new_row = pd.DataFrame([[time_str, product_name, stock_change, single_sales]], columns=columns)

        if os.path.exists(CSV_FILENAME):
            # 读取时指定单笔销量列为 Int64（可处理缺失值）或直接转换为整数
            df_existing = pd.read_csv(CSV_FILENAME, encoding='utf-8-sig')
            # 强制转换单笔销量列为整数（向下取整，并处理 NaN）
            if '单笔销量' in df_existing.columns:
                df_existing['单笔销量'] = df_existing['单笔销量'].fillna(0).astype(int)
        else:
            df_existing = pd.DataFrame(columns=columns)

        # 合并前也确保 new_row 的列类型
        new_row['单笔销量'] = new_row['单笔销量'].astype(int)

        df_updated = pd.concat([df_existing, new_row], ignore_index=True)
        # 最终再强制确保一次
        df_updated['单笔销量'] = df_updated['单笔销量'].fillna(0).astype(int)

        df_updated.to_csv(CSV_FILENAME, index=False, encoding='utf-8-sig')
        git_push_update()
    except Exception as e:
        print(f"❌ 写入 CSV 失败: {e}")


def get_taiwan_stock():
    """获取台湾地址监控目标的当前库存"""
    try:
        resp = requests.get(TAIWAN_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for variant in data.get("variants", []):
            if variant.get("option1") == TAIWAN_TARGET_OPTION:
                qty = variant.get("inventory_quantity")
                return int(qty) if qty is not None else None
        return None
    except Exception as e:
        print(f"❌ 台湾地址请求失败: {e}")
        return None


def get_international_stock():
    """获取国际地址监控成员的当前库存（stockKo.quantity）"""
    try:
        resp = requests.get(INTERNATIONAL_URL, headers=INTERNATIONAL_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for option in data["data"]["optionList"]:
            if option.get("optionNameValue1") == INTERNATIONAL_MEMBER_NAME:
                stock_ko = option.get("stockKo")
                if stock_ko and "quantity" in stock_ko:
                    qty = stock_ko["quantity"]
                    return int(qty) if qty is not None else None
                else:
                    print(f"⚠️ 国际成员 {INTERNATIONAL_MEMBER_NAME} 无有效 stockKo.quantity")
                    return None
        return None
    except Exception as e:
        print(f"❌ 国际地址请求失败: {e}")
        return None


# ==================== 主监控函数 ====================
def monitor_merged():
    # 台湾状态
    taiwan_last_qty = None
    taiwan_initial_logged = False

    # 国际状态
    international_last_qty = None
    international_initial_logged = False

    print(f"📊 启动合并监控，日志文件: {CSV_FILENAME}")
    print(f"🇹🇼 台湾监控: {TAIWAN_TARGET_OPTION} -> 商品名 '{TAIWAN_PRODUCT_NAME}'")
    print(f"🌍 国际监控: {INTERNATIONAL_MEMBER_NAME} -> 商品名 '{INTERNATIONAL_PRODUCT_NAME}'")

    while True:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ---------- 1. 台湾地址 ----------
        taiwan_qty = get_taiwan_stock()
        if taiwan_qty is not None:
            if not taiwan_initial_logged:
                # 初始记录
                taiwan_last_qty = taiwan_qty
                taiwan_initial_logged = True
                print(f"{current_time} [台湾] 初始库存: {taiwan_qty}")
                append_to_csv(current_time, TAIWAN_PRODUCT_NAME, f"初始库存：{taiwan_qty}", abs(taiwan_qty))
            elif taiwan_qty != taiwan_last_qty:
                diff = taiwan_last_qty - taiwan_qty
                print(f"{current_time} [台湾] 变化: {taiwan_last_qty} -> {taiwan_qty}, 销量: {diff}")
                append_to_csv(current_time, TAIWAN_PRODUCT_NAME, f"{taiwan_last_qty} -> {taiwan_qty}", diff)
                taiwan_last_qty = taiwan_qty

        # ---------- 2. 国际地址 ----------
        international_qty = get_international_stock()
        if international_qty is not None:
            if not international_initial_logged:
                international_last_qty = international_qty
                international_initial_logged = True
                print(f"{current_time} [国际] 初始库存: {international_qty}")
                append_to_csv(current_time, INTERNATIONAL_PRODUCT_NAME, f"初始库存：{international_qty}", 0)
            elif international_qty != international_last_qty:
                diff = international_last_qty - international_qty
                print(f"{current_time} [国际] 变化: {international_last_qty} -> {international_qty}, 销量: {diff}")
                append_to_csv(current_time, INTERNATIONAL_PRODUCT_NAME, f"{international_last_qty} -> {international_qty}", diff)
                international_last_qty = international_qty

        time.sleep(10)


if __name__ == "__main__":
    monitor_merged()