import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re

# 目标网站URL
TARGET_URL = "https://jyt.jiangsu.gov.cn/col/col58320/index.html"
SOURCE_NAME = "江苏省教育厅_通知公告"

# ==========================================
# 1. 网页抓取逻辑
# ==========================================
def scrape_data():
    """抓取江苏省教育厅通知公告数据，只抓取前一天发布的文章"""
    policies = []
    all_items = []

    try:
        # 计算前一天日期（使用北京时间 UTC+8）
        tz_utc8 = timezone(timedelta(hours=8))
        today = datetime.now(tz_utc8).date()
        yesterday = today - timedelta(days=1)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }

        response = requests.get(TARGET_URL, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # ——— 方式 A：datastore 脚本标签（江苏政府网通用 CMS 结构）———
        records = []
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and '<datastore>' in script.string:
                recordset_match = re.search(
                    r'<recordset>([\s\S]*?)</recordset>', script.string
                )
                if recordset_match:
                    raw_records = re.findall(
                        r'<record><!\[CDATA\[(.*?)\]\]></record>',
                        recordset_match.group(1),
                        re.DOTALL,
                    )
                    records = raw_records
                break

        # ——— 方式 B：直接解析列表 li 标签（备用） ———
        if not records:
            print("⚠️  未找到 datastore 脚本，尝试直接解析 li 标签")
            items_raw = soup.find_all('li')
            target_count = 0
            filtered_count = 0

            for item in items_raw:
                try:
                    a_tag = item.find('a')
                    if not a_tag:
                        continue

                    title = a_tag.get('title', '').strip() or a_tag.get_text(strip=True)
                    href = a_tag.get('href', '')

                    if not title or len(title) < 5:
                        continue

                    if href.startswith('/'):
                        article_url = 'https://jyt.jiangsu.gov.cn' + href
                    elif not href.startswith('http'):
                        article_url = 'https://jyt.jiangsu.gov.cn/col/col58320/' + href
                    else:
                        article_url = href

                    pub_at = None
                    date_text = item.get_text()
                    date_match = re.search(
                        r'(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})', date_text
                    )
                    if date_match:
                        pub_at = datetime.strptime(
                            f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}",
                            '%Y-%m-%d',
                        ).date()

                    all_items.append({'title': title, 'pub_at': pub_at})

                    if pub_at != yesterday:
                        filtered_count += 1
                        continue

                    target_count += 1
                    content = _fetch_content(article_url, headers)

                    policies.append({
                        'title': title,
                        'url': article_url,
                        'pub_at': pub_at,
                        'content': content,
                        'selected': False,
                        'category': '',
                        'source': '江苏省教育厅通知公告',
                    })
                except Exception:
                    continue

            print(f"✅ 江苏省教育厅通知公告爬虫：成功抓取 {target_count} 条前一天数据")
            print(f"⏭️  过滤掉 {filtered_count} 条非目标日期的数据")
            _print_latest5(all_items)
            return policies, all_items

        # ——— 处理 datastore 记录 ———
        print(f"📋 找到 {len(records)} 篇文章")
        target_count = 0
        filtered_count = 0

        for record in records:
            title_match = re.search(r'title=(["\'])(.*?)\1', record)
            url_match = re.search(r'href=(["\'])(.*?)\1', record)
            date_match = re.search(r'\[(\d{4}-\d{2}-\d{2})\]', record)

            if not all([title_match, url_match, date_match]):
                continue

            title = title_match.group(2)
            href = url_match.group(2)
            date_str = date_match.group(1)

            try:
                pub_at = datetime.strptime(date_str, '%Y-%m-%d').date()
            except Exception:
                continue

            if href.startswith('/'):
                article_url = 'https://jyt.jiangsu.gov.cn' + href
            elif not href.startswith('http'):
                article_url = 'https://jyt.jiangsu.gov.cn/' + href
            else:
                article_url = href

            all_items.append({'title': title, 'pub_at': pub_at})

            if pub_at != yesterday:
                filtered_count += 1
                continue

            target_count += 1
            content = _fetch_content(article_url, headers)

            policies.append({
                'title': title,
                'url': article_url,
                'pub_at': pub_at,
                'content': content,
                'selected': False,
                'category': '',
                'source': '江苏省教育厅通知公告',
            })

        print(f"✅ 江苏省教育厅通知公告爬虫：成功抓取 {target_count} 条前一天数据")
        print(f"⏭️  过滤掉 {filtered_count} 条非目标日期的数据")
        _print_latest5(all_items)

    except Exception as e:
        print(f"❌ 江苏省教育厅通知公告爬虫：抓取失败 - {e}")

    return policies, all_items


def _fetch_content(url, headers):
    """抓取详情页正文内容"""
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        detail_soup = BeautifulSoup(resp.content, 'html.parser')

        # 江苏政府网通用内容容器，按优先级依次尝试
        for selector in [
            '.bt-content.zoom.clearfix',
            '.bt-content',
            '#zoom',
            '.content',
            '#content',
        ]:
            elem = detail_soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # 移除末尾来源信息
                text = re.sub(r'来源：.*$', '', text, flags=re.DOTALL)
                return text
    except Exception as e:
        print(f"⚠️  抓取详情页失败：{url} - {e}")
    return ""


def _print_latest5(all_items):
    """打印最新5条记录（调试用）"""
    if all_items:
        print("📊 页面最新5条是：")
        for item in all_items[:5]:
            date_str = item['pub_at'].strftime('%Y-%m-%d') if item['pub_at'] else '未知日期'
            print(f"✅ {item['title']} {date_str}")


# ==========================================
# 2. 数据入库逻辑
# ==========================================
def save_to_supabase(data_list):
    """保存数据到 Supabase，使用 db_utils 统一处理"""
    try:
        from db_utils import save_to_policy
        return save_to_policy(data_list, SOURCE_NAME)
    except Exception as e:
        print(f"❌ 数据库写入异常: {e}")
        return data_list, None


# ==========================================
# 3. 主函数
# ==========================================
def run():
    """运行江苏省教育厅通知公告爬虫"""
    try:
        data, _ = scrape_data()
        if data:
            result, api_push_result = save_to_supabase(data)
            print(f"💾 写入数据库: {len(result)} 条")
        else:
            result = []
            api_push_result = None
            print("💾 写入数据库: 0 条")
            print("⚠️  未找到目标日期的文章")
        print("----------------------------------------")
        return result, api_push_result
    except Exception as e:
        print(f"❌ 江苏省教育厅通知公告爬虫：运行失败 - {e}")
        print("----------------------------------------")
        return [], None


if __name__ == "__main__":
    run()
