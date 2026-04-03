import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

# 导入数据库工具
from db_utils import save_to_policy

# ==========================================
# 1. 终极配置：带着“暗号”的接口地址
# ==========================================
TARGETS = [
    {
        "name": "江苏省文旅厅_焦点新闻", 
        "columnid": "695", 
        "unitid": "423807",  # 这个是我们刚找到的焦点新闻专属 ID
        "base_url": "https://wlt.jiangsu.gov.cn/col/col695/index.html"
    }
    # ⚠️ 提示：如果你还想爬“文旅资讯(694)”和“通知公告(699)”，
    # 需要你自己用F12按照刚才的方法找一下它们的 unitid，然后按上面的格式加到这里。
]

# Hanweb 系统的标准数据请求接口
PROXY_URL = "https://wlt.jiangsu.gov.cn/module/web/jpage/dataproxy.jsp"

def scrape_data():
    policies = []
    all_items = []
    
    # 获取北京时间昨天日期
    tz_utc8 = timezone(timedelta(hours=8))
    yesterday = (datetime.now(tz_utc8) - timedelta(days=1)).date()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }

    for target in TARGETS:
        print(f"🔍 正在请求接口: {target['name']}")
        
        # 组装接头暗号（参数）
        params = {
            'page': 1,
            'appid': 1,
            'webid': 12,
            'path': '/',
            'columnid': target['columnid'],
            'unitid': target['unitid'],
            'permissiontype': 0
        }
        
        try:
            # 1. 请求数据接口 (带上 params 暗号)
            response = requests.get(PROXY_URL, params=params, headers=headers, timeout=30)
            response.encoding = 'utf-8'
            
            # 2. 正则提取 XML 里的每一条记录
            records = re.findall(r'<record><!\[CDATA\[([\s\S]*?)\]\]></record>', response.text)
            
            for record_html in records:
                soup_item = BeautifulSoup(record_html, 'html.parser')
                a_tag = soup_item.find('a')
                
                # 提取日期 202X-XX-XX
                date_match = re.search(r'202\d-\d{2}-\d{2}', record_html)
                
                if a_tag and date_match:
                    title = a_tag.get('title') or a_tag.get_text(strip=True)
                    href = a_tag.get('href')
                    link = urljoin(target["base_url"], href)
                    pub_at = datetime.strptime(date_match.group(), '%Y-%m-%d').date()
                    
                    item_info = {'title': title, 'pub_at': pub_at, 'url': link}
                    if item_info not in all_items:
                        all_items.append(item_info)

                    # ========================================================
                    # 恢复正式逻辑：只有日期等于昨天，才进入抓取正文和保存环节
                    # ========================================================
                    if pub_at == yesterday: 
                        print(f"✨ 发现昨日目标文章: {title} ({pub_at})")
                        content = ""
                        try:
                            # 抓取详情页正文
                            detail_res = requests.get(link, headers=headers, timeout=20)
                            detail_res.encoding = 'utf-8'
                            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                            
                            # 提取正文
                            content_elem = detail_soup.select_one('#UCAP-CONTENT') or detail_soup.select_one('.bt-content')
                            if content_elem:
                                content = content_elem.get_text(strip=True)
                                print(f"   └─ 成功抓取正文，字数：{len(content)}")
                        except Exception as e:
                            print(f"⚠️ 详情页抓取失败 {link}: {e}")

                        policies.append({
                            'title': title,
                            'url': link,
                            'pub_at': pub_at,
                            'content': content,
                            'source': '江苏省文旅厅',
                            'category': target["name"].split('_')[1]
                        })

        except Exception as e:
            print(f"❌ {target['name']} 接口访问失败: {e}")

    print(f"✅ 江苏省文旅厅本次收集到 {len(policies)} 条待入库数据")
    return policies, all_items

def run():
    try:
        data, all_items = scrape_data()
        
        # 打印最新5条，确认接口提取没问题
        if all_items:
            print("📊 页面最新5条是：")
            for i, item in enumerate(all_items[:5], 1):
                print(f"✅ [{item['pub_at']}] {item['title']}")
        
        # 根据是否有满足日期的数据决定是否保存数据库
        if data:
            save_to_policy(data, "江苏省文旅厅")
            print(f"💾 写入数据库: {len(data)} 条")
            return data
        else:
            print("💾 写入数据库: 0 条 (没有昨日数据)")
            return []
            
    except Exception as e:
        print(f"❌ 文旅厅爬虫运行异常: {e}")
        return []

if __name__ == "__main__":
    run()
