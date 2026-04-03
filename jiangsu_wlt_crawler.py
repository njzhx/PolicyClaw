import os
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

# 导入数据库工具
from db_utils import save_to_policy

# 🌟 引入 Selenium 自动化浏览器
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ==========================================
# 1. 终极配置：直接填网页原地址，不用管接口了！
# ==========================================
TARGETS = [
    {
        "name": "江苏省文旅厅_焦点新闻", 
        "base_url": "https://wlt.jiangsu.gov.cn/col/col695/index.html"
    },
    {
        "name": "江苏省文旅厅_通知公告", 
        "base_url": "https://wlt.jiangsu.gov.cn/col/col699/index.html"
    }
]

def setup_driver():
    """配置并启动无头浏览器 (后台隐身运行)"""
    options = Options()
    options.add_argument('--headless')  # 无头模式，不在屏幕上显示窗口
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox') # Linux 环境必备
    options.add_argument('--disable-dev-shm-usage')
    # 伪装成正常浏览器
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    return webdriver.Chrome(options=options)

def scrape_data():
    policies = []
    all_items = []
    
    tz_utc8 = timezone(timedelta(hours=8))
    yesterday = (datetime.now(tz_utc8) - timedelta(days=1)).date()
    
    print("🚀 正在启动自动化浏览器以突破 521 防护盾...")
    driver = setup_driver()

    try:
        for target in TARGETS:
            print(f"🔍 正在访问: {target['name']}")
            
            # 1. 直接让浏览器打开网页
            driver.get(target['base_url'])
            
            # 🌟 核心魔法：耐心等待 3 秒。
            # 这 3 秒内，浏览器会自动执行那段复杂的 JS，计算出 Cookie，并自动刷新页面！
            time.sleep(3)
            
            # 获取经过浏览器渲染后的真实网页源码
            html = driver.page_source
            
            # 提取原网页隐藏在 script 标签里的 XML 数据
            records = re.findall(r'<record><!\[CDATA\[([\s\S]*?)\]\]></record>', html)
            
            if not records:
                print(f"⚠️ {target['name']} 未提取到数据，请检查。")
                continue
                
            filtered_count = 0

            # 这个列表用来存详情页的链接，避免在循环中直接跳转打断节奏
            to_fetch_details = []

            for record_html in records:
                soup_item = BeautifulSoup(record_html, 'html.parser')
                a_tag = soup_item.find('a')
                date_match = re.search(r'202\d-\d{2}-\d{2}', record_html)
                
                if a_tag and date_match:
                    title = a_tag.get('title') or a_tag.get_text(strip=True)
                    href = a_tag.get('href')
                    link = urljoin(target['base_url'], href)
                    pub_at = datetime.strptime(date_match.group(), '%Y-%m-%d').date()
                    
                    item_info = {'title': title, 'pub_at': pub_at, 'url': link}
                    if item_info not in all_items:
                        all_items.append(item_info)

                    # 如果是昨天的数据，加入待抓取正文列表
                    if pub_at == yesterday:
                        to_fetch_details.append({
                            'title': title,
                            'url': link,
                            'pub_at': pub_at,
                            'source': '江苏省文旅厅',
                            'category': target["name"].split('_')[1]
                        })
                    else:
                        filtered_count += 1
                        
            # 2. 依次去抓取详情页正文（同样使用浏览器，完美绕过防护）
            for item in to_fetch_details:
                print(f"✨ 发现目标文章，正在抓取正文: {item['title']}")
                content = ""
                try:
                    driver.get(item['url'])
                    time.sleep(2) # 给页面一点加载时间
                    detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                    
                    content_elem = detail_soup.select_one('#UCAP-CONTENT') or detail_soup.select_one('.bt-content')
                    if content_elem:
                        content = content_elem.get_text(strip=True)
                except Exception as e:
                    print(f"⚠️ 详情页抓取失败: {e}")
                
                item['content'] = content
                policies.append(item)

            print(f"⏭️  {target['name']}：过滤掉 {filtered_count} 条非目标日期的数据")

    except Exception as e:
        print(f"❌ 爬虫运行发生异常: {e}")
    finally:
        # 务必关闭浏览器，释放内存
        driver.quit()

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
