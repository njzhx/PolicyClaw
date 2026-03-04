import time
import sys
from datetime import datetime
from io import StringIO

# 导入飞书通知模块
try:
    from feishu_notifier import send_crawler_result
except ImportError:
    send_crawler_result = None


class DualOutput:
    """双输出流，同时输出到控制台和缓冲区"""
    
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
        self.buffer = StringIO()
    
    def write(self, text):
        self.original_stdout.write(text)
        self.buffer.write(text)
    
    def flush(self):
        self.original_stdout.flush()
        self.buffer.flush()
    
    def getvalue(self):
        return self.buffer.getvalue()


# ==========================================
# 爬虫管理系统
# 功能：执行多个爬虫，一个爬虫出错不影响其他爬虫
# ==========================================

class CrawlerManager:
    def __init__(self):
        """初始化爬虫管理器"""
        self.crawlers = []
        self.results = {}
    
    def register_crawler(self, name, crawler_func, crawler_module):
        """注册爬虫
        
        Args:
            name: 爬虫名称
            crawler_func: 爬虫执行函数
            crawler_module: 爬虫模块对象，用于获取 TARGET_URL
        """
        target_url = getattr(crawler_module, 'TARGET_URL', '')
        self.crawlers.append((name, crawler_func, target_url))
        if target_url:
            print(f"✅ 已注册爬虫: {name} ({target_url})")
        else:
            print(f"✅ 已注册爬虫: {name}")
    
    def run_all_crawlers(self):
        """执行所有爬虫
        
        Returns:
            dict: 各爬虫执行结果
        """
        # 开始捕获输出
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        dual_out = DualOutput(original_stdout)
        dual_err = DualOutput(original_stderr)
        sys.stdout = dual_out
        sys.stderr = dual_err
        
        start_datetime = datetime.now()
        print(f"\n🚀 开始执行爬虫任务 - {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        total_start_time = time.time()
        
        for name, crawler_func, target_url in self.crawlers:
            if target_url:
                print(f"\n📦 开始执行爬虫: {name}")
                print(f"🔗 目标网址: {target_url}")

            else:
                print(f"\n📦 开始执行爬虫: {name}")
            print("-" * 40)
            
            start_time = time.time()
            
            try:
                # 执行爬虫
                result = crawler_func()
                
                # 记录结果
                execution_time = time.time() - start_time
                
                # 区分抓取数量和写入数量
                # 处理可能的元组返回值（包含API推送结果）
                crawl_count = 0
                write_count = 0
                api_push_result = None
                
                if isinstance(result, tuple) and len(result) == 2:
                    data_list, api_push_result = result
                    crawl_count = len(data_list)
                    write_count = len(data_list)
                else:
                    data_list = result
                    crawl_count = len(data_list)
                    write_count = len(data_list)
                
                self.results[name] = {
                    'status': 'success',
                    'crawl_count': crawl_count,
                    'write_count': write_count,
                    'execution_time': round(execution_time, 2),
                    'timestamp': datetime.now().isoformat(),
                    'target_url': target_url,
                    'api_push_result': api_push_result
                }
                
                print(f"✅ 爬虫 {name} 执行成功")
                print(f"📊 抓取数据: {crawl_count} 条")
                print(f"💾 写入数据库: {crawl_count} 条")
                print(f"⏱️  执行时间: {round(execution_time, 2)} 秒")
                
            except Exception as e:
                # 捕获异常，确保其他爬虫继续执行
                execution_time = time.time() - start_time
                self.results[name] = {
                    'status': 'error',
                    'crawl_count': 0,
                    'write_count': 0,
                    'error_message': str(e),
                    'execution_time': round(execution_time, 2),
                    'timestamp': datetime.now().isoformat(),
                    'target_url': target_url
                }
                
                print(f"❌ 爬虫 {name} 执行失败")
                print(f"💥 错误信息: {str(e)}")
                print(f"📊 抓取数据: 0 条")
                print(f"💾 写入数据库: 0 条")
                print(f"⏱️  执行时间: {round(execution_time, 2)} 秒")
            
            print("-" * 40)
        
        total_execution_time = time.time() - total_start_time
        end_datetime = datetime.now()
        
        print("=" * 60)
        print(f"📋 爬虫执行完成 - {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  总执行时间: {round(total_execution_time, 2)} 秒")
        print(f"📦 执行爬虫数: {len(self.crawlers)}")
        
        # 统计结果
        success_count = sum(1 for r in self.results.values() if r['status'] == 'success')
        error_count = sum(1 for r in self.results.values() if r['status'] == 'error')
        
        # 统计总抓取和写入数量
        total_crawl = sum(r.get('crawl_count', 0) for r in self.results.values())
        total_write = sum(r.get('write_count', 0) for r in self.results.values())
        
        print(f"✅ 成功: {success_count} 个")
        print(f"❌ 失败: {error_count} 个")
        print(f"📊 总抓取数据: {total_crawl} 条")
        print(f"💾 总写入数据库: {total_write} 条")
        
        # 获取完整日志
        full_log = dual_out.getvalue() + dual_err.getvalue()
        
        # 恢复标准输出
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        
        # 输出API推送结果
        print("\n📡 API推送结果:")
        print("-" * 40)
        api_success_count = 0
        api_error_count = 0
        
        for crawler_name, result in self.results.items():
            if result['status'] == 'success' and 'api_push_result' in result:
                api_result = result['api_push_result']
                if api_result:
                    status = api_result.get('status', 'unknown')
                    message = api_result.get('message', '')
                    if status == 'success':
                        print(f"✅ {crawler_name}：{message}")
                        api_success_count += 1
                    elif status == 'error':
                        print(f"❌ {crawler_name}：{message}")
                        api_error_count += 1
                    else:
                        print(f"⚠️  {crawler_name}：{message}")
        
        if api_success_count == 0 and api_error_count == 0:
            print("⚠️  没有API推送记录")
        else:
            print(f"📊 API推送统计: 成功 {api_success_count} 个, 失败 {api_error_count} 个")
        print("-" * 40)
        
        # 推送每日状态数据到API
        try:
            from db_utils import push_daily_status
            date_str = start_datetime.date().isoformat()
            daily_success_count = total_crawl  # 使用总抓取数量作为成功数
            daily_fail_count = error_count  # 使用失败的爬虫数作为失败数
            print("\n📅 推送每日状态数据...")
            daily_status_result = push_daily_status(date_str, daily_success_count, daily_fail_count)
            if isinstance(daily_status_result, dict):
                status = daily_status_result.get('status', 'unknown')
                message = daily_status_result.get('message', '')
                if status == 'success':
                    print(f"✅ 每日状态数据推送成功：{message}")
                else:
                    print(f"❌ 每日状态数据推送失败：{message}")
        except Exception as e:
            print(f"⚠️  推送每日状态数据时发生错误：{e}")
        
        # 发送飞书通知
        if send_crawler_result:
            print("\n📤 正在发送飞书通知...")
            send_crawler_result(self.results, start_datetime, end_datetime, full_log)
        
        return self.results
    
    def get_summary(self):
        """获取执行摘要"""
        if not self.results:
            return "尚未执行爬虫任务"
        
        summary = []
        for name, result in self.results.items():
            if result['status'] == 'success':
                summary.append(f"✅ {name}: 抓取 {result['crawl_count']} 条，写入数据库 {result['write_count']} 条")
            else:
                summary.append(f"❌ {name}: 执行失败 - {result['error_message'][:100]}...")
        
        return "\n".join(summary)

# ==========================================
# 主执行逻辑
# ==========================================
if __name__ == "__main__":
    # 创建爬虫管理器
    manager = CrawlerManager()
    
    # 注册爬虫
    # 注意：这里需要根据实际爬虫模块进行导入和注册
    try:
        # 导入中国政府网爬虫
        import gov_crawler
        manager.register_crawler("中国政府网", gov_crawler.run, gov_crawler)
        
        # 导入中国政府网政策解读爬虫
        import gov_interpretation_crawler
        manager.register_crawler("中国政府网政策解读", gov_interpretation_crawler.run, gov_interpretation_crawler)
        
        # 导入国家发改委爬虫
        import ndrc_crawler
        manager.register_crawler("国家发改委", ndrc_crawler.run, ndrc_crawler)
        
        # 导入人民网财经爬虫
        # import people_finance_crawler
        # manager.register_crawler("人民网财经", people_finance_crawler.run, people_finance_crawler)
        
        # 注册 mubiao.md 中的16个新爬虫
        try:
            import miit_wjk_crawler
            manager.register_crawler("工信部_文件库", miit_wjk_crawler.run, miit_wjk_crawler)
        except ImportError as e:
            print(f"⚠️  导入工信部_文件库爬虫失败: {e}")
        
        try:
            import miit_zcjd_crawler
            manager.register_crawler("工信部_政策解读", miit_zcjd_crawler.run, miit_zcjd_crawler)
        except ImportError as e:
            print(f"⚠️  导入工信部_政策解读爬虫失败: {e}")
        
        try:
            import nda_zwgk_crawler
            manager.register_crawler("数据局_政务公开", nda_zwgk_crawler.run, nda_zwgk_crawler)
        except ImportError as e:
            print(f"⚠️  导入数据局_政务公开爬虫失败: {e}")
        
        try:
            import mohurd_wjk_crawler
            manager.register_crawler("住建部_文件库", mohurd_wjk_crawler.run, mohurd_wjk_crawler)
        except ImportError as e:
            print(f"⚠️  导入住建部_文件库爬虫失败: {e}")
        
        try:
            import jiangsu_gov_zxwj_crawler
            manager.register_crawler("省政府_最新文件", jiangsu_gov_zxwj_crawler.run, jiangsu_gov_zxwj_crawler)
        except ImportError as e:
            print(f"⚠️  导入省政府_最新文件爬虫失败: {e}")
        
        try:
            import jiangsu_gov_zcjd_crawler
            manager.register_crawler("省政府_政策解读", jiangsu_gov_zcjd_crawler.run, jiangsu_gov_zcjd_crawler)
        except ImportError as e:
            print(f"⚠️  导入省政府_政策解读爬虫失败: {e}")
        
        try:
            import jiangsu_gov_gb_crawler
            manager.register_crawler("省政府_省政府公报", jiangsu_gov_gb_crawler.run, jiangsu_gov_gb_crawler)
        except ImportError as e:
            print(f"⚠️  导入省政府_省政府公报爬虫失败: {e}")
        
        try:
            import jiangsu_fzggw_zcwj_crawler
            manager.register_crawler("省发改委_政策文件", jiangsu_fzggw_zcwj_crawler.run, jiangsu_fzggw_zcwj_crawler)
        except ImportError as e:
            print(f"⚠️  导入省发改委_政策文件爬虫失败: {e}")
        
        try:
            import jiangsu_fzggw_zcjd_crawler
            manager.register_crawler("省发改委_政策解读", jiangsu_fzggw_zcjd_crawler.run, jiangsu_fzggw_zcjd_crawler)
        except ImportError as e:
            print(f"⚠️  导入省发改委_政策解读爬虫失败: {e}")
        
        try:
            import jiangsu_fzggw_tzgg_crawler
            manager.register_crawler("省发改委_通知公告", jiangsu_fzggw_tzgg_crawler.run, jiangsu_fzggw_tzgg_crawler)
        except ImportError as e:
            print(f"⚠️  导入省发改委_通知公告爬虫失败: {e}")
        
        try:
            import jiangsu_gxt_gsgg_crawler
            manager.register_crawler("省工信厅_公示公告", jiangsu_gxt_gsgg_crawler.run, jiangsu_gxt_gsgg_crawler)
        except ImportError as e:
            print(f"⚠️  导入省工信厅_公示公告爬虫失败: {e}")
        
        try:
            import jiangsu_gxt_wjtz_crawler
            manager.register_crawler("省工信厅_文件通知", jiangsu_gxt_wjtz_crawler.run, jiangsu_gxt_wjtz_crawler)
        except ImportError as e:
            print(f"⚠️  导入省工信厅_文件通知爬虫失败: {e}")
        
        try:
            import jiangsu_gxt_zcwj_crawler
            manager.register_crawler("省工信厅_政策文件", jiangsu_gxt_zcwj_crawler.run, jiangsu_gxt_zcwj_crawler)
        except ImportError as e:
            print(f"⚠️  导入省工信厅_政策文件爬虫失败: {e}")
        
        try:
            import jiangsu_sjj_zcfb_crawler
            manager.register_crawler("省数据局_政策发布", jiangsu_sjj_zcfb_crawler.run, jiangsu_sjj_zcfb_crawler)
        except ImportError as e:
            print(f"⚠️  导入省数据局_政策发布爬虫失败: {e}")
        
        try:
            import jiangsu_sjj_zcjd_crawler
            manager.register_crawler("省数据局_政策解读", jiangsu_sjj_zcjd_crawler.run, jiangsu_sjj_zcjd_crawler)
        except ImportError as e:
            print(f"⚠️  导入省数据局_政策解读爬虫失败: {e}")
        
        try:
            import jiangsu_czt_gg_crawler
            manager.register_crawler("财政厅_公告", jiangsu_czt_gg_crawler.run, jiangsu_czt_gg_crawler)
        except ImportError as e:
            print(f"⚠️  导入财政厅_公告爬虫失败: {e}")
        
    except ImportError as e:
        print(f"⚠️  导入爬虫模块失败: {e}")
    
    # 执行所有爬虫
    if manager.crawlers:
        results = manager.run_all_crawlers()
        
        # 打印执行摘要
        print("\n📊 执行摘要:")
        print("=" * 60)
        print(manager.get_summary())
    else:
        print("⚠️  没有注册任何爬虫")
