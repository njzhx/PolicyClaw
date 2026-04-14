import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re

# 目标网站URL - 江苏省交通运输厅 政策文件
TARGET_URL = "https://jtyst.jiangsu.gov.cn/col/col77151/index.html"
SOURCE_NAME = "江苏省交通运输厅_政策文件"

# ==========================================
# 1. 网页抓取逻辑
# ==========================================
def scrape_data():
    """抓取数据，返回与表结构一致的字典列表"""
    policies = []
    all_items = 0
    
    try:
        # 【标准设定】计算前一天日期（北京时间 UTC+8）
        tz_utc8 = timezone(timedelta(hours=8))
        today = datetime.now(tz_utc8).date()
        yesterday = today - timedelta(days=1)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        response = requests.get(TARGET_URL, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8' # 交通厅通常使用utf-8
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # 寻找包含 <record> 的脚本块
        datastore_script = next((s.string for s in soup.find_all('script') if s.string and '<record>' in s.string), None)
        
        if not datastore_script:
            print(f"❌ [{SOURCE_NAME}] 未找到datastore脚本")
            return policies, all_items
        
        # 提取 XML 记录
        records = re.findall(r'<record><!\[CDATA\[(.*?)\]\]></record>', datastore_script, re.DOTALL)
        all_items = len(records)
        print(f"📋 [{SOURCE_NAME}] 找到 {all_items} 篇文章")
        
        target_date_items = 0
        
        for record in records:
            title_match = re.search(r'title=(["\'])(.*?)\1', record)
            url_match = re.search(r'href=(["\'])(.*?)\1', record)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', record)
            
            if not all([title_match, url_match, date_match]):
                continue
            
            title = title_match.group(2)
            url = url_match.group(2)
            date_str = date_match.group(1)
            pub_at = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # 【严格匹配昨日日期】
            if pub_at == yesterday:
                target_date_items += 1
                # 处理相对路径
                if not url.startswith('http'):
                    url = f"https://jtyst.jiangsu.gov.cn{url}" if url.startswith('/') else f"https://jtyst.jiangsu.gov.cn/{url}"
                
                # 抓取详情页
                content = ""
                try:
                    d_res = requests.get(url, headers=headers, timeout=15)
                    d_res.encoding = 'utf-8'
                    d_soup = BeautifulSoup(d_res.text, 'html.parser')
                    
                    # 匹配内容主体（交通厅常用 #zoom 或 .main-txt）
                    c_elem = d_soup.select_one('#zoom') or d_soup.select_one('.main-txt')
                    if c_elem:
                        # 移除脚本、样式、图片及打印干扰
                        for extra in c_elem.select('script, style, img, .printer, .newnewerm'):
                            extra.decompose()
                        content = c_elem.get_text(strip=True)
                        # 清洗常见干扰后缀
                        content = re.sub(r'浏览次数：.*$|来源：.*$|打印本页.*$|发布日期：.*$', '', content, flags=re.MULTILINE)
                except Exception as e:
                    print(f"⚠️ 详情抓取失败: {url} - {e}")
                
                policies.append({
                    'title': title,
                    'url': url,
                    'pub_at': pub_at,
                    'content': content,
                    'selected': False,
                    'category': '',
                    'source': SOURCE_NAME
                })
        
        print(f"✅ [{SOURCE_NAME}]：抓取到 {target_date_items} 条昨日数据")
        
    except Exception as e:
        print(f"❌ [{SOURCE_NAME}] 运行失败 - {e}")
    
    return policies, all_items

# ==========================================
# 2. 数据入库逻辑
# ==========================================
def save_to_supabase(data_list):
    """对接数据库工具类"""
    try:
        from db_utils import save_to_policy
        return save_to_policy(data_list, SOURCE_NAME)
    except Exception:
        return data_list, None

# ==========================================
# 3. 主函数
# ==========================================
def run():
    try:
        data, _ = scrape_data()
        if data:
            result, _ = save_to_supabase(data)
            print(f"💾 写入数据库: {len(result)} 条")
            return result
        else:
            print("💾 写入数据库: 0 条 (今日无更新)")
            return []
    except Exception as e:
        print(f"❌ 运行报错 - {e}")
        return []

if __name__ == "__main__":
    run()
