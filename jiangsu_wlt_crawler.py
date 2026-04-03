import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

# 导入你项目原有的数据库工具
from db_utils import save_to_policy

# 定义要抓取的三个目标页面
TARGETS = [
    {"name": "江苏省文旅厅_文旅资讯", "url": "https://wlt.jiangsu.gov.cn/col/col694/index.html"},
    {"name": "江苏省文旅厅_焦点新闻", "url": "https://wlt.jiangsu.gov.cn/col/col695/index.html"},
    {"name": "江苏省文旅厅_通知公告", "url": "https://wlt.jiangsu.gov.cn/col/col699/index.html"}
]

def scrape_data():
    policies = []
    all_items = []
    
    # 获取北京时间昨天日期
    tz_utc8 = timezone(timedelta(hours=8))
    yesterday = (datetime.now(tz_utc8) - timedelta(days=1)).date()
    
    for target in TARGETS:
        try:
            # 伪装成浏览器，防止被拦截
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(target["url"], headers=headers, timeout=30)
            response.encoding = 'utf-8'
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 找到所有的超链接标签
            links = soup.find_all('a')
            
            for a_tag in links:
                title = a_tag.get('title') or a_tag.get_text(strip=True)
                href = a_tag.get('href')
                
                # 过滤掉无效链接
                if not title or not href or 'javascript' in href or len(title) < 5:
                    continue
                    
                # 尝试从 a 标签所在的整个父节点（通常是 <li> 或 <tr>）中提取日期
                parent_text = a_tag.parent.get_text(strip=True)
                
                # 使用正则表达式精准提取 202X-XX-XX 格式的日期
                match = re.search(r'202\d-\d{2}-\d{2}', parent_text)
                
                if match:
                    date_str = match.group()
                    pub_at = datetime.strptime(date_str, '%Y-%m-%d').date()
                    link = urljoin(target["url"], href)
                    
                    item_data = {'title': title, 'pub_at': pub_at, 'url': link}
                    
                    # 简单去重，防止同一个页面里有重复链接
                    if item_data not in all_items:
                        all_items.append(item_data)
                        
                        # 核心逻辑：只保留昨天的数据
                        if pub_at == yesterday:
                            policies.append({
                                'title': title,
                                'url': link,
                                'pub_at': pub_at,
                                'content': '', 
                                'category': target["name"].split('_')[1], # 自动填入是“文旅资讯”还是“通知公告”
                                'source': '江苏省文旅厅'
                            })
                            
        except Exception as e:
            print(f"❌ {target['name']} 抓取失败: {e}")
            
    print(f"✅ 江苏省文旅厅：成功抓取 {len(policies)} 条昨日数据")
    
    # 打印前5条便于你在日志里确认是否抓对
    if all_items:
        print("📊 页面最新5条是：")
        for i, item in enumerate(all_items[:5], 1):
            date_str = item['pub_at'].strftime('%Y-%m-%d')
            print(f"✅ {item['title']} {date_str}")
            
    return policies, all_items

def run():
    data, _ = scrape_data()
    if data:
        save_to_policy(data, "江苏省文旅厅")
    return data
