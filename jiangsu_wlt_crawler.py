import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

# 导入数据库工具
from db_utils import save_to_policy

# ==========================================
# 1. 终极配置：双栏目抓取
# ==========================================
TARGETS = [
    {
        "name": "江苏省文旅厅_焦点新闻", 
        "columnid": "695", 
        "unitid": "423807", 
        "base_url": "https://wlt.jiangsu.gov.cn/col/col695/index.html"
    },
    {
        "name": "江苏省文旅厅_通知公告", 
        "columnid": "699", 
        "unitid": "423807", 
        "base_url": "https://wlt.jiangsu.gov.cn/col/col699/index.html"
    }
]

def scrape_data():
    policies = []
    all_items = []
    
    # 获取北京时间昨天日期
    tz_utc8 = timezone(timedelta(hours=8))
    yesterday = (datetime.now(tz_utc8) - timedelta(days=1)).date()
    
    # 🌟 装备 1：开启长连接会话（维持 Cookie）
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
    })

    # 先访问一下主页，骗取防火墙的初始 Cookie (忽略任何报错)
    try:
        session.get('https://wlt.jiangsu.gov.cn/', timeout=10)
    except:
        pass

    for target in TARGETS:
        if not target["unitid"].isdigit():
            continue

        print(f"🔍 正在请求接口: {target['name']}")
        
        # 🌟 装备 2：增加防盗链标识
        session.headers.update({'Referer': target['base_url']})
        
        # 🌟 装备 3：使用网页原生的备用链接（纯 GET 请求）
        request_url = (
            f"https://wlt.jiangsu.gov.cn/module/web/jpage/dataproxy.jsp?"
            f"page=1&appid=1&webid=12&path=/&columnid={target['columnid']}&"
            f"unitid={target['unitid']}&"
            f"webname=%25E6%25B1%259F%25E8%258B%258F%25E7%259C%2581%25E6%2596%2587%25E5%258C%2596%25E5%2592%258C%25E6%2597%2585%25E6%25B8%25B8%25E5%258E%2585&"
            f"permissiontype=0"
        )
        
        try:
            response = session.get(request_url, timeout=30)
            response.encoding = 'utf-8'
            
            records = re.findall(r'<record><!\[CDATA\[([\s\S]*?)\]\]></record>', response.text)
            
            # 🕵️‍♂️ 终极排错：如果没抓到数据，看看服务器到底返回了什么鬼！
            if not records:
                print(f"⚠️ 接口未能返回有效文章。HTTP状态码: {response.status_code}")
                print(f"🛑 服务器实际返回内容(前200字)如下：\n{response.text[:200]}")
                print("-" * 40)
                continue
                
            filtered_count = 0

            for record_html in records:
                soup_item = BeautifulSoup(record_html, 'html.parser')
                a_tag = soup_item.find('a')
                date_match = re.search(r'202\d-\d{2}-\d{2}', record_html)
                
                if a_tag and date_match:
                    title = a_tag.get('title') or a_tag.get_text(strip=True)
                    href = a_tag.get('href')
                    link = urljoin(target["base_url"], href)
                    pub_at = datetime.strptime(date_match.group(), '%Y-%m-%d').date()
                    
                    item_info = {'title': title, 'pub_at': pub_at, 'url': link}
                    if item_info not in all_items:
                        all_items.append(item_info)

                    # 严格日期判断逻辑：只抓昨天的数据
                    if pub_at == yesterday: 
                        content = ""
                        try:
                            # 详情页也使用 session 访问
                            detail_res = session.get(link, timeout=20)
                            detail_res.encoding = 'utf-8'
                            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                            
                            content_elem = detail_soup.select_one('#UCAP-CONTENT') or detail_soup.select_one('.bt-content')
                            if content_elem:
                                content = content_elem.get_text(strip=True)
                        except Exception as e:
                            print(f"⚠️ 详情页抓取失败 {link}: {e}")

                        category_name = target["name"].split('_')[1]
                        policies.append({
                            'title': title,
                            'url': link,
                            'pub_at': pub_at,
                            'content': content,
                            'source': '江苏省文旅厅',
                            'category': category_name
                        })
                    else:
                        filtered_count += 1
                        
            if records:
                print(f"⏭️  {target['name']}：过滤掉 {filtered_count} 条非目标日期的数据")

        except Exception as e:
            print(f"❌ {target['name']} 接口访问失败: {e}")

    print(f"✅ 江苏省文旅厅爬虫：成功抓取 {len(policies)} 条前一天数据")
    
    if all_items:
        print("📊 页面最新5条是：")
        for i, item in enumerate(all_items[:5], 1):
            date_str = item['pub_at'].strftime('%Y-%m-%d') if item['pub_at'] else '未知日期'
            print(f"✅ {item['title']} {date_str}")
            
    return policies, all_items

def run():
    try:
        data, _ = scrape_data()
        
        if data:
            save_to_policy(data, "江苏省文旅厅")
            print(f"💾 写入数据库: {len(data)} 条")
            return data
        else:
            print("💾 写入数据库: 0 条 (没有符合日期的数据)")
            return []
            
    except Exception as e:
        print(f"❌ 文旅厅爬虫运行异常: {e}")
        return []

if __name__ == "__main__":
    run()
