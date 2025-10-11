"""
人民日报新闻摘要自动化系统
这个文件包含了从爬取、处理、审核到发送的所有逻辑
作者：张三
最后修改：2024-03-15
TODO: 需要重构，代码太乱了
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
import logging
import re
from typing import List, Dict, Any
import hashlib
from pathlib import Path

# 全局变量（不太好的做法，但是先这样吧）
BASE_URL = "http://paper.people.com.cn/rmrb/html/"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxxxxxxxxxxxx")
OPENAI_BASE_URL = "https://api.openai.com/v1"
DB_PATH = "subscribers.db"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = os.getenv("EMAIL_USER", "your_email@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your_password")
LOG_FILE = "news_digest.log"
MAX_CHUNK_SIZE = 3000  # 每篇文章的最大字符数
SUMMARY_PROMPT = "请用200字以内总结以下新闻内容："
REVIEW_PROMPT = "请审核以下新闻摘要，检查是否有敏感内容、错误信息或不当表达。如果没有问题，回复'通过'；如果有问题，请详细说明："

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def get_todays_paper_url():
    """获取今天的报纸URL"""
    today = datetime.now()
    year = today.strftime("%Y-%m")
    day = today.strftime("%d")
    url = f"{BASE_URL}{year}/{day}/nbs.D110000renmrb_01.htm"
    logger.info(f"构建的报纸URL: {url}")
    return url


def crawl_peoples_daily():
    """
    爬取人民日报网站
    返回文章列表
    """
    logger.info("开始爬取人民日报...")
    url = get_todays_paper_url()
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            logger.error(f"请求失败，状态码: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找所有文章链接
        articles = []
        article_links = soup.find_all('a', href=re.compile(r'nw\.D110000renmrb_\d+\.htm'))
        
        logger.info(f"找到 {len(article_links)} 篇文章")
        
        for idx, link in enumerate(article_links[:20]):  # 限制只爬前20篇
            try:
                article_url = link['href']
                if not article_url.startswith('http'):
                    # 构建完整URL
                    base = url.rsplit('/', 1)[0]
                    article_url = f"{base}/{article_url}"
                
                title = link.get_text(strip=True)
                logger.info(f"正在爬取第 {idx+1} 篇: {title}")
                
                # 获取文章内容
                article_response = requests.get(article_url, headers=headers, timeout=20)
                article_response.encoding = 'utf-8'
                article_soup = BeautifulSoup(article_response.text, 'html.parser')
                
                # 提取正文
                content_div = article_soup.find('div', class_='article')
                if not content_div:
                    content_div = article_soup.find('div', id='ozoom')
                
                if content_div:
                    paragraphs = content_div.find_all('p')
                    content = '\n'.join([p.get_text(strip=True) for p in paragraphs])
                else:
                    content = ""
                
                if content and len(content) > 50:  # 过滤太短的内容
                    articles.append({
                        'title': title,
                        'content': content,
                        'url': article_url,
                        'crawl_time': datetime.now().isoformat()
                    })
                
                time.sleep(1)  # 避免请求过快
                
            except Exception as e:
                logger.error(f"爬取文章 {idx+1} 失败: {str(e)}")
                continue
        
        logger.info(f"成功爬取 {len(articles)} 篇文章")
        return articles
        
    except Exception as e:
        logger.error(f"爬取失败: {str(e)}")
        return []


def split_content_into_chunks(content: str, max_size: int = MAX_CHUNK_SIZE) -> List[str]:
    """
    将长文本分割成多个chunk
    这个函数写得不太好，但是能用
    """
    chunks = []
    current_chunk = ""
    
    # 按段落分割
    paragraphs = content.split('\n')
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 <= max_size:
            if current_chunk:
                current_chunk += '\n' + para
            else:
                current_chunk = para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks if chunks else [content[:max_size]]


def call_llm_api(prompt: str, content: str, model: str = "gpt-3.5-turbo") -> str:
    """
    调用大语言模型API
    这里混合了总结和审核的逻辑，不太好分离
    """
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一个专业的新闻编辑助手。"},
                {"role": "user", "content": f"{prompt}\n\n{content}"}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            logger.error(f"API调用失败: {response.status_code} - {response.text}")
            return ""
            
    except Exception as e:
        logger.error(f"调用LLM API失败: {str(e)}")
        return ""


def summarize_articles(articles: List[Dict]) -> List[Dict]:
    """
    对文章进行总结
    这个函数太长了，应该拆分
    """
    logger.info("开始总结文章...")
    summarized_articles = []
    
    for idx, article in enumerate(articles):
        try:
            logger.info(f"正在总结第 {idx+1}/{len(articles)} 篇: {article['title']}")
            
            content = article['content']
            title = article['title']
            
            # 如果文章太长，分chunk处理
            if len(content) > MAX_CHUNK_SIZE:
                chunks = split_content_into_chunks(content)
                logger.info(f"文章过长，分为 {len(chunks)} 个chunk")
                
                chunk_summaries = []
                for chunk_idx, chunk in enumerate(chunks):
                    logger.info(f"  处理chunk {chunk_idx+1}/{len(chunks)}")
                    summary = call_llm_api(SUMMARY_PROMPT, chunk)
                    if summary:
                        chunk_summaries.append(summary)
                    time.sleep(2)  # API限流
                
                # 如果有多个chunk的摘要，再次总结
                if len(chunk_summaries) > 1:
                    combined_summary = '\n'.join(chunk_summaries)
                    final_summary = call_llm_api(
                        "请将以下多个摘要合并为一个连贯的总结（200字以内）：",
                        combined_summary
                    )
                    if not final_summary:
                        final_summary = '\n'.join(chunk_summaries[:3])  # 降级方案
                else:
                    final_summary = chunk_summaries[0] if chunk_summaries else "总结生成失败"
            else:
                # 直接总结
                final_summary = call_llm_api(SUMMARY_PROMPT, content)
                if not final_summary:
                    final_summary = content[:200] + "..."  # 降级方案
            
            summarized_articles.append({
                'title': title,
                'summary': final_summary,
                'url': article['url'],
                'original_length': len(content),
                'summary_time': datetime.now().isoformat()
            })
            
            time.sleep(3)  # 避免API调用过快
            
        except Exception as e:
            logger.error(f"总结文章 {idx+1} 失败: {str(e)}")
            # 添加一个失败记录
            summarized_articles.append({
                'title': article.get('title', 'Unknown'),
                'summary': '总结生成失败',
                'url': article.get('url', ''),
                'original_length': len(article.get('content', '')),
                'summary_time': datetime.now().isoformat(),
                'error': str(e)
            })
    
    logger.info(f"完成总结，共 {len(summarized_articles)} 篇")
    return summarized_articles


def concatenate_summaries(summarized_articles: List[Dict]) -> str:
    """
    拼接所有摘要
    简单粗暴的字符串拼接
    """
    logger.info("拼接摘要...")
    
    digest = "# 今日人民日报新闻摘要\n\n"
    digest += f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n"
    digest += "---\n\n"
    
    for idx, article in enumerate(summarized_articles, 1):
        digest += f"## {idx}. {article['title']}\n\n"
        digest += f"{article['summary']}\n\n"
        digest += f"[阅读原文]({article['url']})\n\n"
        digest += "---\n\n"
    
    digest += f"\n共 {len(summarized_articles)} 篇新闻\n"
    
    logger.info(f"摘要拼接完成，总长度: {len(digest)} 字符")
    return digest


def review_content(digest: str) -> Dict[str, Any]:
    """
    审核内容
    调用LLM进行审核
    """
    logger.info("开始内容审核...")
    
    try:
        # 如果内容太长，只审核前5000字
        content_to_review = digest[:5000] if len(digest) > 5000 else digest
        
        review_result = call_llm_api(REVIEW_PROMPT, content_to_review, model="gpt-4")
        
        if not review_result:
            logger.warning("审核API返回空结果，默认通过")
            return {
                'passed': True,
                'message': '审核API无响应，默认通过',
                'review_time': datetime.now().isoformat()
            }
        
        # 简单判断是否通过
        passed = '通过' in review_result or 'pass' in review_result.lower()
        
        logger.info(f"审核结果: {'通过' if passed else '未通过'}")
        logger.info(f"审核意见: {review_result}")
        
        return {
            'passed': passed,
            'message': review_result,
            'review_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"审核失败: {str(e)}")
        return {
            'passed': True,  # 审核失败默认通过
            'message': f'审核过程出错: {str(e)}',
            'review_time': datetime.now().isoformat()
        }


def init_database():
    """
    初始化数据库
    创建订阅者表
    """
    logger.info("初始化数据库...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            status TEXT DEFAULT 'active',
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_sent_at TIMESTAMP,
            send_count INTEGER DEFAULT 0
        )
    ''')
    
    # 插入一些测试数据
    test_subscribers = [
        ('user1@example.com', '张三', 'active'),
        ('user2@example.com', '李四', 'active'),
        ('user3@example.com', '王五', 'inactive'),
        ('user4@example.com', '赵六', 'active'),
        ('user5@example.com', '孙七', 'paused'),
    ]
    
    for email, name, status in test_subscribers:
        try:
            cursor.execute(
                'INSERT OR IGNORE INTO subscribers (email, name, status) VALUES (?, ?, ?)',
                (email, name, status)
            )
        except:
            pass
    
    conn.commit()
    conn.close()
    logger.info("数据库初始化完成")


def get_active_subscribers() -> List[Dict[str, str]]:
    """
    获取所有激活的订阅者
    这里直接操作数据库，没有用ORM
    """
    logger.info("获取活跃订阅者列表...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, name, subscribed_at, last_sent_at, send_count
            FROM subscribers
            WHERE status = 'active'
            ORDER BY subscribed_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        subscribers = []
        for row in rows:
            subscribers.append({
                'id': row[0],
                'email': row[1],
                'name': row[2] or 'Unknown',
                'subscribed_at': row[3],
                'last_sent_at': row[4],
                'send_count': row[5] or 0
            })
        
        logger.info(f"找到 {len(subscribers)} 个活跃订阅者")
        return subscribers
        
    except Exception as e:
        logger.error(f"获取订阅者失败: {str(e)}")
        return []


def send_email(to_email: str, to_name: str, subject: str, content: str) -> bool:
    """
    发送邮件
    使用SMTP协议
    """
    try:
        logger.info(f"发送邮件到 {to_email} ({to_name})")
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f"新闻摘要助手 <{EMAIL_USER}>"
        msg['To'] = f"{to_name} <{to_email}>"
        msg['Subject'] = subject
        
        # 转换markdown为HTML（简单版本）
        html_content = content.replace('\n', '<br>')
        html_content = re.sub(r'## (.*?)<br>', r'<h2>\1</h2>', html_content)
        html_content = re.sub(r'# (.*?)<br>', r'<h1>\1</h1>', html_content)
        html_content = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html_content)
        html_content = re.sub(r'---<br>', r'<hr>', html_content)
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                h1 {{ color: #d32f2f; }}
                h2 {{ color: #1976d2; margin-top: 20px; }}
                hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
                a {{ color: #1976d2; text-decoration: none; }}
            </style>
        </head>
        <body>
            {html_content}
            <br><br>
            <p style="color: #999; font-size: 12px;">
                如需取消订阅，请回复 UNSUBSCRIBE<br>
                本邮件由自动化系统发送，请勿直接回复
            </p>
        </body>
        </html>
        """
        
        text_part = MIMEText(content, 'plain', 'utf-8')
        html_part = MIMEText(html_body, 'html', 'utf-8')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # 连接SMTP服务器
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"邮件发送成功: {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"发送邮件到 {to_email} 失败: {str(e)}")
        return False


def update_subscriber_send_status(subscriber_id: int, success: bool):
    """
    更新订阅者的发送状态
    直接SQL操作
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if success:
            cursor.execute('''
                UPDATE subscribers
                SET last_sent_at = ?,
                    send_count = send_count + 1
                WHERE id = ?
            ''', (datetime.now().isoformat(), subscriber_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"更新订阅者状态失败: {str(e)}")


def send_to_subscribers(digest: str):
    """
    发送给所有订阅者
    这个函数太长了，混合了太多逻辑
    """
    logger.info("开始群发邮件...")
    
    subscribers = get_active_subscribers()
    
    if not subscribers:
        logger.warning("没有活跃订阅者，跳过发送")
        return
    
    subject = f"人民日报新闻摘要 - {datetime.now().strftime('%Y年%m月%d日')}"
    
    success_count = 0
    fail_count = 0
    
    for subscriber in subscribers:
        try:
            success = send_email(
                to_email=subscriber['email'],
                to_name=subscriber['name'],
                subject=subject,
                content=digest
            )
            
            if success:
                success_count += 1
                update_subscriber_send_status(subscriber['id'], True)
            else:
                fail_count += 1
                update_subscriber_send_status(subscriber['id'], False)
            
            # 避免发送过快
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"处理订阅者 {subscriber['email']} 时出错: {str(e)}")
            fail_count += 1
    
    logger.info(f"邮件发送完成: 成功 {success_count}, 失败 {fail_count}")


def save_digest_to_file(digest: str, review_result: Dict):
    """
    保存摘要到文件
    用于备份和审计
    """
    try:
        output_dir = Path("digests")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"digest_{timestamp}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(digest)
            f.write("\n\n---\n\n")
            f.write(f"## 审核信息\n\n")
            f.write(f"审核结果: {'通过' if review_result['passed'] else '未通过'}\n")
            f.write(f"审核意见: {review_result['message']}\n")
            f.write(f"审核时间: {review_result['review_time']}\n")
        
        logger.info(f"摘要已保存到: {filename}")
        
        # 同时保存JSON格式
        json_filename = output_dir / f"digest_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({
                'digest': digest,
                'review': review_result,
                'timestamp': timestamp
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"JSON格式已保存到: {json_filename}")
        
    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}")


def generate_statistics(articles: List[Dict], subscribers: List[Dict]) -> str:
    """
    生成统计信息
    这个函数本来不需要，但是后来加上了
    """
    stats = f"""
    
## 统计信息

- 爬取文章数: {len(articles)}
- 活跃订阅者: {len(subscribers)}
- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 总字符数: {sum(len(a.get('summary', '')) for a in articles)}
    """
    return stats


def main():
    """
    主函数
    串联所有流程
    这个函数太长了，包含了太多步骤
    """
    logger.info("=" * 50)
    logger.info("新闻摘要系统启动")
    logger.info("=" * 50)
    
    start_time = time.time()
    
    try:
        # 第一步：初始化数据库
        init_database()
        
        # 第二步：爬取人民日报
        articles = crawl_peoples_daily()
        if not articles:
            logger.error("没有爬取到文章，退出")
            return
        
        logger.info(f"成功爬取 {len(articles)} 篇文章")
        
        # 第三步：分篇喂给大语言模型总结
        summarized_articles = summarize_articles(articles)
        if not summarized_articles:
            logger.error("没有生成摘要，退出")
            return
        
        # 第四步：拼接总结
        digest = concatenate_summaries(summarized_articles)
        
        # 添加统计信息
        subscribers = get_active_subscribers()
        stats = generate_statistics(summarized_articles, subscribers)
        digest += stats
        
        # 第五步：喂给大语言模型审核
        review_result = review_content(digest)
        
        # 保存到文件
        save_digest_to_file(digest, review_result)
        
        # 第六步：如果审核通过，发送给订阅者
        if review_result['passed']:
            logger.info("审核通过，准备发送邮件")
            send_to_subscribers(digest)
        else:
            logger.warning("审核未通过，不发送邮件")
            logger.warning(f"审核意见: {review_result['message']}")
        
        # 计算耗时
        elapsed_time = time.time() - start_time
        logger.info(f"任务完成，总耗时: {elapsed_time:.2f} 秒")
        
        # 打印摘要预览
        print("\n" + "=" * 50)
        print("摘要预览（前500字符）:")
        print("=" * 50)
        print(digest[:500])
        print("...\n")
        
    except Exception as e:
        logger.error(f"主流程执行失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    logger.info("=" * 50)
    logger.info("新闻摘要系统结束")
    logger.info("=" * 50)


# 一些工具函数，后来加的，放在最后
def add_subscriber(email: str, name: str = None):
    """添加订阅者"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO subscribers (email, name, status) VALUES (?, ?, ?)',
            (email, name, 'active')
        )
        conn.commit()
        conn.close()
        logger.info(f"成功添加订阅者: {email}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"订阅者已存在: {email}")
        return False
    except Exception as e:
        logger.error(f"添加订阅者失败: {str(e)}")
        return False


def remove_subscriber(email: str):
    """删除订阅者"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM subscribers WHERE email = ?', (email,))
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        
        if affected_rows > 0:
            logger.info(f"成功删除订阅者: {email}")
            return True
        else:
            logger.warning(f"订阅者不存在: {email}")
            return False
    except Exception as e:
        logger.error(f"删除订阅者失败: {str(e)}")
        return False


def update_subscriber_status(email: str, status: str):
    """更新订阅者状态"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE subscribers SET status = ? WHERE email = ?',
            (status, email)
        )
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        
        if affected_rows > 0:
            logger.info(f"成功更新订阅者状态: {email} -> {status}")
            return True
        else:
            logger.warning(f"订阅者不存在: {email}")
            return False
    except Exception as e:
        logger.error(f"更新订阅者状态失败: {str(e)}")
        return False


def list_all_subscribers():
    """列出所有订阅者"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM subscribers ORDER BY subscribed_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        print("\n所有订阅者:")
        print("-" * 80)
        for row in rows:
            print(f"ID: {row[0]}, Email: {row[1]}, Name: {row[2]}, Status: {row[3]}, Subscribed: {row[4]}")
        print("-" * 80)
        
        return rows
    except Exception as e:
        logger.error(f"列出订阅者失败: {str(e)}")
        return []


# 命令行接口（后来加的，有点乱）
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "run":
            main()
        elif command == "add":
            if len(sys.argv) >= 3:
                email = sys.argv[2]
                name = sys.argv[3] if len(sys.argv) >= 4 else None
                add_subscriber(email, name)
            else:
                print("用法: python script.py add <email> [name]")
        elif command == "remove":
            if len(sys.argv) >= 3:
                email = sys.argv[2]
                remove_subscriber(email)
            else:
                print("用法: python script.py remove <email>")
        elif command == "list":
            list_all_subscribers()
        elif command == "status":
            if len(sys.argv) >= 4:
                email = sys.argv[2]
                status = sys.argv[3]
                update_subscriber_status(email, status)
            else:
                print("用法: python script.py status <email> <active|inactive|paused>")
        elif command == "test-email":
            if len(sys.argv) >= 3:
                email = sys.argv[2]
                test_content = "# 测试邮件\n\n这是一封测试邮件。\n\n如果您收到此邮件，说明邮件系统工作正常。"
                send_email(email, "测试用户", "测试邮件", test_content)
            else:
                print("用法: python script.py test-email <email>")
        elif command == "crawl-only":
            # 只爬取，不处理
            articles = crawl_peoples_daily()
            print(f"\n成功爬取 {len(articles)} 篇文章")
            for idx, article in enumerate(articles, 1):
                print(f"{idx}. {article['title']} ({len(article['content'])} 字)")
        elif command == "init-db":
            init_database()
            print("数据库初始化完成")
        else:
            print("未知命令:", command)
            print("\n可用命令:")
            print("  run           - 运行完整流程")
            print("  add           - 添加订阅者")
            print("  remove        - 删除订阅者")
            print("  list          - 列出所有订阅者")
            print("  status        - 更新订阅者状态")
            print("  test-email    - 发送测试邮件")
            print("  crawl-only    - 仅爬取文章")
            print("  init-db       - 初始化数据库")
    else:
        # 默认运行主流程
        main()


# 全局异常处理器（最后加的，用来捕获未处理的异常）
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """全局异常处理"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.error("未捕获的异常:", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = global_exception_handler


# 一些常量定义（应该放在文件开头的，但是忘了）
RETRY_TIMES = 3
RETRY_DELAY = 5
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
]


# 缓存机制（后来想加的，但是没完成）
CACHE_DIR = Path("cache")
CACHE_EXPIRY = 3600  # 1小时


def get_cache_key(url: str) -> str:
    """生成缓存key"""
    return hashlib.md5(url.encode()).hexdigest()
"""
这些是从主文件中提取的繁琐实现的函数
可以直接复制到主文件中替换对应的pass实现
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import re

logger = logging.getLogger(__name__)

# 这些常量应该在主文件开头定义
CACHE_DIR = Path("cache")
CACHE_EXPIRY = 3600  # 1小时


def get_from_cache(key: str):
    """
    从缓存获取
    这个函数实现得很繁琐，有很多冗余检查
    """
    try:
        # 先检查缓存目录是否存在
        if not CACHE_DIR.exists():
            logger.debug(f"缓存目录不存在: {CACHE_DIR}")
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                logger.info(f"创建缓存目录: {CACHE_DIR}")
            except Exception as e:
                logger.error(f"创建缓存目录失败: {str(e)}")
                return None
        
        # 检查缓存目录是否可读
        if not os.access(CACHE_DIR, os.R_OK):
            logger.warning(f"缓存目录不可读: {CACHE_DIR}")
            return None
        
        # 验证key是否为空
        if not key:
            logger.warning("缓存key为空")
            return None
        
        # 验证key格式（必须是MD5）
        if not re.match(r'^[a-f0-9]{32}$', key):
            logger.warning(f"无效的缓存key格式: {key}")
            return None
        
        # 构建缓存文件路径
        cache_file = CACHE_DIR / f"{key}.cache"
        metadata_file = CACHE_DIR / f"{key}.meta"
        
        # 检查缓存文件是否存在
        if not cache_file.exists():
            logger.debug(f"缓存未命中: {key}")
            return None
        
        # 检查元数据文件是否存在
        if not metadata_file.exists():
            logger.warning(f"缓存元数据文件不存在: {key}")
            # 删除无效的缓存文件
            try:
                cache_file.unlink()
                logger.info(f"删除无效缓存文件: {cache_file}")
            except Exception as e:
                logger.error(f"删除缓存文件失败: {str(e)}")
            return None
        
        # 读取元数据
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_content = f.read()
                if not metadata_content:
                    logger.warning(f"元数据文件为空: {key}")
                    return None
                metadata = json.loads(metadata_content)
        except json.JSONDecodeError as e:
            logger.error(f"元数据JSON解析失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"读取元数据失败: {str(e)}")
            return None
        
        # 验证元数据结构
        required_fields = ['created_at', 'expires_at', 'key', 'size']
        for field in required_fields:
            if field not in metadata:
                logger.warning(f"元数据缺少必需字段: {field}")
                return None
        
        # 检查key是否匹配
        if metadata.get('key') != key:
            logger.warning(f"元数据key不匹配: {metadata.get('key')} != {key}")
            return None
        
        # 检查是否过期
        try:
            expires_at = datetime.fromisoformat(metadata['expires_at'])
            now = datetime.now()
            
            if now > expires_at:
                logger.info(f"缓存已过期: {key}")
                # 删除过期的缓存
                try:
                    cache_file.unlink()
                    metadata_file.unlink()
                    logger.info(f"删除过期缓存: {key}")
                except Exception as e:
                    logger.error(f"删除过期缓存失败: {str(e)}")
                return None
        except ValueError as e:
            logger.error(f"时间戳解析失败: {str(e)}")
            return None
        
        # 读取缓存数据
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = f.read()
                
            # 验证数据不为空
            if not cached_data:
                logger.warning(f"缓存数据为空: {key}")
                return None
            
            # 验证数据大小
            actual_size = len(cached_data)
            expected_size = metadata.get('size', 0)
            if actual_size != expected_size:
                logger.warning(f"缓存数据大小不匹配: {actual_size} != {expected_size}")
                # 数据可能损坏，删除缓存
                try:
                    cache_file.unlink()
                    metadata_file.unlink()
                except Exception as e:
                    logger.error(f"删除损坏缓存失败: {str(e)}")
                return None
            
            # 尝试解析JSON
            try:
                data = json.loads(cached_data)
            except json.JSONDecodeError:
                # 如果不是JSON，返回原始字符串
                data = cached_data
            
            logger.info(f"缓存命中: {key}")
            
            # 更新访问统计（如果有的话）
            metadata['last_accessed'] = datetime.now().isoformat()
            metadata['access_count'] = metadata.get('access_count', 0) + 1
            try:
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"更新元数据失败: {str(e)}")
            
            return data
            
        except Exception as e:
            logger.error(f"读取缓存数据失败: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"从缓存获取数据时发生未知错误: {str(e)}")
        return None


def save_to_cache(key: str, data):
    """
    保存到缓存
    这个函数也实现得很繁琐，有大量的验证逻辑
    """
    try:
        # 验证输入参数
        if not key:
            logger.warning("缓存key为空，无法保存")
            return False
        
        if data is None:
            logger.warning("缓存数据为None，无法保存")
            return False
        
        # 验证key格式
        if not re.match(r'^[a-f0-9]{32}$', key):
            logger.warning(f"无效的缓存key格式: {key}")
            return False
        
        # 确保缓存目录存在
        if not CACHE_DIR.exists():
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                logger.info(f"创建缓存目录: {CACHE_DIR}")
            except Exception as e:
                logger.error(f"创建缓存目录失败: {str(e)}")
                return False
        
        # 检查目录权限
        if not os.access(CACHE_DIR, os.W_OK):
            logger.error(f"缓存目录不可写: {CACHE_DIR}")
            return False
        
        # 检查磁盘空间（简单检查）
        try:
            stat = os.statvfs(CACHE_DIR)
            free_space = stat.f_bavail * stat.f_frsize
            min_free_space = 100 * 1024 * 1024  # 100MB
            if free_space < min_free_space:
                logger.warning(f"磁盘空间不足: {free_space / 1024 / 1024:.2f}MB")
                # 清理旧缓存
                try:
                    clean_old_cache_files(max_age_hours=1)
                except Exception as e:
                    logger.error(f"清理旧缓存失败: {str(e)}")
        except Exception as e:
            logger.warning(f"检查磁盘空间失败: {str(e)}")
        
        # 序列化数据
        try:
            if isinstance(data, str):
                serialized_data = data
            elif isinstance(data, (dict, list)):
                serialized_data = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                # 尝试转换为字符串
                serialized_data = str(data)
        except Exception as e:
            logger.error(f"序列化数据失败: {str(e)}")
            return False
        
        # 验证序列化后的数据
        if not serialized_data:
            logger.warning("序列化后的数据为空")
            return False
        
        # 检查数据大小
        data_size = len(serialized_data)
        max_cache_size = 10 * 1024 * 1024  # 10MB
        if data_size > max_cache_size:
            logger.warning(f"缓存数据过大: {data_size / 1024 / 1024:.2f}MB")
            return False
        
        # 构建文件路径
        cache_file = CACHE_DIR / f"{key}.cache"
        metadata_file = CACHE_DIR / f"{key}.meta"
        temp_cache_file = CACHE_DIR / f"{key}.cache.tmp"
        temp_metadata_file = CACHE_DIR / f"{key}.meta.tmp"
        
        # 创建元数据
        created_at = datetime.now()
        expires_at = created_at + timedelta(seconds=CACHE_EXPIRY)
        
        metadata = {
            'key': key,
            'created_at': created_at.isoformat(),
            'expires_at': expires_at.isoformat(),
            'size': data_size,
            'type': type(data).__name__,
            'access_count': 0,
            'version': '1.0'
        }
        
        # 先写入临时文件，避免写入过程中断导致数据损坏
        try:
            # 写入临时缓存文件
            with open(temp_cache_file, 'w', encoding='utf-8') as f:
                f.write(serialized_data)
                f.flush()
                os.fsync(f.fileno())  # 确保写入磁盘
            
            # 验证临时文件
            if not temp_cache_file.exists():
                logger.error(f"临时缓存文件创建失败: {temp_cache_file}")
                return False
            
            # 检查临时文件大小
            actual_temp_size = temp_cache_file.stat().st_size
            if actual_temp_size != data_size:
                logger.error(f"临时文件大小不匹配: {actual_temp_size} != {data_size}")
                temp_cache_file.unlink()
                return False
            
            # 写入临时元数据文件
            with open(temp_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # 验证临时元数据文件
            if not temp_metadata_file.exists():
                logger.error(f"临时元数据文件创建失败: {temp_metadata_file}")
                temp_cache_file.unlink()
                return False
            
        except Exception as e:
            logger.error(f"写入临时文件失败: {str(e)}")
            # 清理临时文件
            try:
                if temp_cache_file.exists():
                    temp_cache_file.unlink()
                if temp_metadata_file.exists():
                    temp_metadata_file.unlink()
            except Exception as cleanup_error:
                logger.error(f"清理临时文件失败: {str(cleanup_error)}")
            return False
        
        # 原子性地替换旧文件
        try:
            # 如果旧缓存存在，先备份
            if cache_file.exists():
                backup_file = CACHE_DIR / f"{key}.cache.bak"
                try:
                    cache_file.rename(backup_file)
                except Exception as e:
                    logger.warning(f"备份旧缓存失败: {str(e)}")
            
            if metadata_file.exists():
                backup_meta_file = CACHE_DIR / f"{key}.meta.bak"
                try:
                    metadata_file.rename(backup_meta_file)
                except Exception as e:
                    logger.warning(f"备份旧元数据失败: {str(e)}")
            
            # 重命名临时文件为正式文件
            temp_cache_file.rename(cache_file)
            temp_metadata_file.rename(metadata_file)
            
            # 验证最终文件
            if not cache_file.exists() or not metadata_file.exists():
                logger.error("缓存文件重命名后验证失败")
                return False
            
            # 删除备份文件
            backup_file = CACHE_DIR / f"{key}.cache.bak"
            backup_meta_file = CACHE_DIR / f"{key}.meta.bak"
            try:
                if backup_file.exists():
                    backup_file.unlink()
                if backup_meta_file.exists():
                    backup_meta_file.unlink()
            except Exception as e:
                logger.warning(f"删除备份文件失败: {str(e)}")
            
            logger.info(f"成功保存缓存: {key} ({data_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"替换缓存文件失败: {str(e)}")
            # 尝试恢复备份
            backup_file = CACHE_DIR / f"{key}.cache.bak"
            backup_meta_file = CACHE_DIR / f"{key}.meta.bak"
            try:
                if backup_file.exists():
                    backup_file.rename(cache_file)
                if backup_meta_file.exists():
                    backup_meta_file.rename(metadata_file)
                logger.info("已恢复备份缓存")
            except Exception as restore_error:
                logger.error(f"恢复备份失败: {str(restore_error)}")
            return False
            
    except Exception as e:
        logger.error(f"保存缓存时发生未知错误: {str(e)}")
        return False


def clean_old_cache_files(max_age_hours: int = 24):
    """清理旧的缓存文件"""
    try:
        if not CACHE_DIR.exists():
            return
        
        now = datetime.now()
        deleted_count = 0
        
        for cache_file in CACHE_DIR.glob("*.cache"):
            try:
                # 获取文件修改时间
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                age_hours = (now - mtime).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    key = cache_file.stem
                    metadata_file = CACHE_DIR / f"{key}.meta"
                    
                    cache_file.unlink()
                    if metadata_file.exists():
                        metadata_file.unlink()
                    
                    deleted_count += 1
            except Exception as e:
                logger.error(f"删除缓存文件 {cache_file} 失败: {str(e)}")
        
        logger.info(f"清理了 {deleted_count} 个旧缓存文件")
    except Exception as e:
        logger.error(f"清理缓存失败: {str(e)}")


# 配置管理相关
CONFIG = {
    'max_articles': 20,
    'chunk_size': 3000,
    'retry_times': 3,
    'api_timeout': 60,
    'email_batch_size': 10,
    'log_level': 'INFO',
}


def load_config():
    """
    加载配置
    从多个来源加载，优先级很混乱
    """
    global CONFIG
    
    logger.info("开始加载配置...")
    
    # 1. 首先尝试从配置文件加载
    config_file = Path("config.json")
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                logger.info(f"从配置文件加载了 {len(file_config)} 个配置项")
                # 逐个更新配置
                for key, value in file_config.items():
                    if key in CONFIG:
                        old_value = CONFIG[key]
                        CONFIG[key] = value
                        logger.debug(f"配置项 {key}: {old_value} -> {value}")
                    else:
                        logger.warning(f"未知的配置项: {key}")
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {str(e)}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
    else:
        logger.info("配置文件不存在，使用默认配置")
    
    # 2. 从环境变量覆盖配置（优先级更高）
    env_prefix = "NEWS_DIGEST_"
    for key in CONFIG.keys():
        env_key = f"{env_prefix}{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            old_value = CONFIG[key]
            # 尝试转换类型
            try:
                if isinstance(CONFIG[key], int):
                    CONFIG[key] = int(env_value)
                elif isinstance(CONFIG[key], float):
                    CONFIG[key] = float(env_value)
                elif isinstance(CONFIG[key], bool):
                    CONFIG[key] = env_value.lower() in ('true', '1', 'yes')
                else:
                    CONFIG[key] = env_value
                logger.info(f"环境变量覆盖配置 {key}: {old_value} -> {CONFIG[key]}")
            except ValueError as e:
                logger.error(f"环境变量 {env_key} 类型转换失败: {str(e)}")
    
    # 3. 验证配置的合法性
    if CONFIG['max_articles'] < 1:
        logger.warning("max_articles 不能小于1，重置为1")
        CONFIG['max_articles'] = 1
    if CONFIG['max_articles'] > 100:
        logger.warning("max_articles 不能大于100，重置为100")
        CONFIG['max_articles'] = 100
    
    if CONFIG['chunk_size'] < 100:
        logger.warning("chunk_size 过小，重置为1000")
        CONFIG['chunk_size'] = 1000
    if CONFIG['chunk_size'] > 10000:
        logger.warning("chunk_size 过大，重置为5000")
        CONFIG['chunk_size'] = 5000
    
    if CONFIG['retry_times'] < 0:
        CONFIG['retry_times'] = 0
    if CONFIG['retry_times'] > 10:
        logger.warning("retry_times 过大，重置为10")
        CONFIG['retry_times'] = 10
    
    if CONFIG['api_timeout'] < 10:
        logger.warning("api_timeout 过小，重置为30")
        CONFIG['api_timeout'] = 30
    
    if CONFIG['email_batch_size'] < 1:
        CONFIG['email_batch_size'] = 1
    if CONFIG['email_batch_size'] > 100:
        logger.warning("email_batch_size 过大，重置为50")
        CONFIG['email_batch_size'] = 50
    
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if CONFIG['log_level'] not in valid_log_levels:
        logger.warning(f"无效的日志级别: {CONFIG['log_level']}，重置为INFO")
        CONFIG['log_level'] = 'INFO'
    
    # 应用日志级别
    try:
        numeric_level = getattr(logging, CONFIG['log_level'])
        logging.getLogger().setLevel(numeric_level)
        logger.info(f"日志级别设置为: {CONFIG['log_level']}")
    except Exception as e:
        logger.error(f"设置日志级别失败: {str(e)}")
    
    logger.info("配置加载完成")
    logger.debug(f"当前配置: {json.dumps(CONFIG, indent=2)}")
    
    return CONFIG


def save_config():
    """
    保存配置到文件
    繁琐的保存过程，有备份机制
    """
    try:
        config_file = Path("config.json")
        temp_config_file = Path("config.json.tmp")
        backup_config_file = Path("config.json.bak")
        
        logger.info("开始保存配置...")
        
        # 1. 先写入临时文件
        try:
            with open(temp_config_file, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, ensure_ascii=False, indent=2)
                f.write('\n')  # 添加结尾换行符
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"写入临时配置文件失败: {str(e)}")
            if temp_config_file.exists():
                try:
                    temp_config_file.unlink()
                except:
                    pass
            return False
        
        # 2. 验证临时文件
        try:
            with open(temp_config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                if loaded_config != CONFIG:
                    logger.error("临时配置文件验证失败：内容不匹配")
                    temp_config_file.unlink()
                    return False
        except Exception as e:
            logger.error(f"验证临时配置文件失败: {str(e)}")
            if temp_config_file.exists():
                temp_config_file.unlink()
            return False
        
        # 3. 备份旧配置文件
        if config_file.exists():
            try:
                if backup_config_file.exists():
                    backup_config_file.unlink()
                config_file.rename(backup_config_file)
                logger.info("已备份旧配置文件")
            except Exception as e:
                logger.warning(f"备份配置文件失败: {str(e)}")
        
        # 4. 重命名临时文件为正式文件
        try:
            temp_config_file.rename(config_file)
            logger.info(f"配置已保存到: {config_file}")
        except Exception as e:
            logger.error(f"重命名配置文件失败: {str(e)}")
            # 尝试恢复备份
            if backup_config_file.exists():
                try:
                    backup_config_file.rename(config_file)
                    logger.info("已恢复备份配置文件")
                except Exception as restore_error:
                    logger.error(f"恢复备份失败: {str(restore_error)}")
            return False
        
        # 5. 清理旧备份（保留最新的3个）
        try:
            backup_files = sorted(
                Path(".").glob("config.json.bak*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for old_backup in backup_files[3:]:
                try:
                    old_backup.unlink()
                    logger.debug(f"删除旧备份: {old_backup}")
                except Exception as e:
                    logger.warning(f"删除旧备份失败: {str(e)}")
        except Exception as e:
            logger.warning(f"清理旧备份失败: {str(e)}")
        
        return True
        
    except Exception as e:
        logger.error(f"保存配置时发生未知错误: {str(e)}")
        return False


# 性能监控类
class PerformanceMonitor:
    """
    性能监控类
    实现得很繁琐，但是功能还算完整
    """
    def __init__(self):
        self.metrics = {}
        self.start_times = {}
        self.counters = {}
        self.history = []
        self.max_history = 1000
        logger.info("性能监控器初始化")
    
    def start_timing(self, name: str):
        """开始计时"""
        if not name:
            logger.warning("计时名称为空")
            return
        
        self.start_times[name] = time.time()
        logger.debug(f"开始计时: {name}")
    
    def end_timing(self, name: str):
        """结束计时并记录"""
        if not name:
            logger.warning("计时名称为空")
            return
        
        if name not in self.start_times:
            logger.warning(f"未找到计时起点: {name}")
            return
        
        elapsed = time.time() - self.start_times[name]
        self.record(name, elapsed)
        del self.start_times[name]
        logger.debug(f"结束计时: {name} = {elapsed:.3f}s")
    
    def record(self, name: str, value: float):
        """记录一个指标值"""
        if not name:
            logger.warning("指标名称为空")
            return
        
        if value is None:
            logger.warning(f"指标值为None: {name}")
            return
        
        try:
            value = float(value)
        except (ValueError, TypeError) as e:
            logger.error(f"指标值转换失败: {name} = {value}, {str(e)}")
            return
        
        # 初始化指标结构
        if name not in self.metrics:
            self.metrics[name] = {
                'count': 0,
                'sum': 0,
                'min': float('inf'),
                'max': float('-inf'),
                'values': []
            }
        
        # 更新统计信息
        metric = self.metrics[name]
        metric['count'] += 1
        metric['sum'] += value
        metric['min'] = min(metric['min'], value)
        metric['max'] = max(metric['max'], value)
        metric['values'].append(value)
        
        # 限制值列表大小
        if len(metric['values']) > 100:
            metric['values'] = metric['values'][-100:]
        
        # 添加到历史记录
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'name': name,
            'value': value
        })
        
        # 限制历史记录大小
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        logger.debug(f"记录指标: {name} = {value}")
    
    def increment(self, name: str, amount: int = 1):
        """增加计数器"""
        if not name:
            logger.warning("计数器名称为空")
            return
        
        if name not in self.counters:
            self.counters[name] = 0
        
        self.counters[name] += amount
        logger.debug(f"计数器增加: {name} +{amount} = {self.counters[name]}")
    
    def get_metric(self, name: str):
        """获取指标统计"""
        if name not in self.metrics:
            logger.warning(f"指标不存在: {name}")
            return None
        
        metric = self.metrics[name]
        count = metric['count']
        
        if count == 0:
            return {
                'count': 0,
                'avg': 0,
                'min': 0,
                'max': 0,
                'sum': 0
            }
        
        return {
            'count': count,
            'avg': metric['sum'] / count,
            'min': metric['min'],
            'max': metric['max'],
            'sum': metric['sum']
        }
    
    def report(self):
        """生成性能报告"""
        try:
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append("性能监控报告")
            report_lines.append("=" * 60)
            report_lines.append("")
            
            # 报告计时指标
            if self.metrics:
                report_lines.append("## 计时指标")
                report_lines.append("")
                for name, metric in sorted(self.metrics.items()):
                    stats = self.get_metric(name)
                    report_lines.append(f"### {name}")
                    report_lines.append(f"  次数: {stats['count']}")
                    report_lines.append(f"  平均: {stats['avg']:.3f}s")
                    report_lines.append(f"  最小: {stats['min']:.3f}s")
                    report_lines.append(f"  最大: {stats['max']:.3f}s")
                    report_lines.append(f"  总计: {stats['sum']:.3f}s")
                    report_lines.append("")
            
            # 报告计数器
            if self.counters:
                report_lines.append("## 计数器")
                report_lines.append("")
                for name, count in sorted(self.counters.items()):
                    report_lines.append(f"  {name}: {count}")
                report_lines.append("")
            
            # 报告历史记录统计
            if self.history:
                report_lines.append("## 历史记录")
                report_lines.append(f"  总记录数: {len(self.history)}")
                report_lines.append(f"  最早记录: {self.history[0]['timestamp']}")
                report_lines.append(f"  最新记录: {self.history[-1]['timestamp']}")
                report_lines.append("")
            
            report_lines.append("=" * 60)
            
            report = "\n".join(report_lines)
            logger.info(f"\n{report}")
            
            # 同时保存到文件
            try:
                report_file = Path("performance_report.txt")
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                logger.info(f"性能报告已保存到: {report_file}")
            except Exception as e:
                logger.error(f"保存性能报告失败: {str(e)}")
            
            return report
            
        except Exception as e:
            logger.error(f"生成性能报告失败: {str(e)}")
            return ""
    
    def reset(self):
        """重置所有统计数据"""
        try:
            self.metrics.clear()
            self.start_times.clear()
            self.counters.clear()
            self.history.clear()
            logger.info("性能监控数据已重置")
        except Exception as e:
            logger.error(f"重置性能监控数据失败: {str(e)}")


# 更多工具函数...
def clean_old_logs(days=7):
    """
    清理旧日志
    删除超过指定天数的日志文件
    """
    try:
        log_dir = Path(".")
        cutoff_time = datetime.now() - timedelta(days=days)
        deleted_count = 0
        total_size = 0
        
        logger.info(f"开始清理 {days} 天前的日志文件...")
        
        # 查找所有日志文件
        log_patterns = ["*.log", "*.log.*", "news_digest*.log"]
        log_files = []
        
        for pattern in log_patterns:
            log_files.extend(log_dir.glob(pattern))
        
        # 去重
        log_files = list(set(log_files))
        
        logger.info(f"找到 {len(log_files)} 个日志文件")
        
        for log_file in log_files:
            try:
                # 跳过当前正在使用的日志文件
                if log_file.name == LOG_FILE:
                    logger.debug(f"跳过当前日志文件: {log_file}")
                    continue
                
                # 检查文件修改时间
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                
                if mtime < cutoff_time:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    deleted_count += 1
                    total_size += file_size
                    logger.info(f"删除旧日志: {log_file} ({file_size / 1024:.2f} KB)")
                else:
                    logger.debug(f"保留日志文件: {log_file}")
                    
            except Exception as e:
                logger.error(f"删除日志文件 {log_file} 失败: {str(e)}")
        
        logger.info(f"清理完成: 删除 {deleted_count} 个文件，释放 {total_size / 1024 / 1024:.2f} MB空间")
        return deleted_count
        
    except Exception as e:
        logger.error(f"清理日志失败: {str(e)}")
        return 0


def backup_database():
    """
    备份数据库
    创建数据库的备份副本
    """
    try:
        import shutil
        
        db_file = Path(DB_PATH)
        
        if not db_file.exists():
            logger.warning(f"数据库文件不存在: {db_file}")
            return False
        
        # 创建备份目录
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        # 生成备份文件名（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"subscribers_{timestamp}.db"
        
        logger.info(f"开始备份数据库: {db_file} -> {backup_file}")
        
        # 复制数据库文件
        shutil.copy2(db_file, backup_file)
        
        # 验证备份
        if not backup_file.exists():
            logger.error("备份文件创建失败")
            return False
        
        backup_size = backup_file.stat().st_size
        original_size = db_file.stat().st_size
        
        if backup_size != original_size:
            logger.warning(f"备份文件大小不一致: {backup_size} != {original_size}")
        
        logger.info(f"数据库备份成功: {backup_file} ({backup_size / 1024:.2f} KB)")
        
        # 清理旧备份（保留最近10个）
        try:
            backup_files = sorted(
                backup_dir.glob("subscribers_*.db"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            for old_backup in backup_files[10:]:
                try:
                    old_backup.unlink()
                    logger.info(f"删除旧备份: {old_backup}")
                except Exception as e:
                    logger.warning(f"删除旧备份失败: {str(e)}")
                    
        except Exception as e:
            logger.warning(f"清理旧备份失败: {str(e)}")
        
        return True
        
    except Exception as e:
        logger.error(f"备份数据库失败: {str(e)}")
        return False


def generate_report():
    """
    生成运行报告
    汇总系统运行状态和统计信息
    """
    try:
        import sqlite3
        
        logger.info("开始生成运行报告...")
        
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("新闻摘要系统运行报告")
        report_lines.append("=" * 70)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 1. 系统信息
        report_lines.append("## 系统信息")
        report_lines.append("")
        report_lines.append(f"  Python版本: {os.sys.version.split()[0]}")
        report_lines.append(f"  工作目录: {os.getcwd()}")
        report_lines.append(f"  配置文件: {'存在' if Path('config.json').exists() else '不存在'}")
        report_lines.append(f"  数据库文件: {'存在' if Path(DB_PATH).exists() else '不存在'}")
        report_lines.append("")
        
        # 2. 配置信息
        report_lines.append("## 当前配置")
        report_lines.append("")
        for key, value in CONFIG.items():
            report_lines.append(f"  {key}: {value}")
        report_lines.append("")
        
        # 3. 数据库统计
        report_lines.append("## 订阅者统计")
        report_lines.append("")
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 总订阅者数
            cursor.execute('SELECT COUNT(*) FROM subscribers')
            total_subscribers = cursor.fetchone()[0]
            report_lines.append(f"  总订阅者数: {total_subscribers}")
            
            # 按状态统计
            cursor.execute('SELECT status, COUNT(*) FROM subscribers GROUP BY status')
            status_stats = cursor.fetchall()
            for status, count in status_stats:
                report_lines.append(f"  {status} 状态: {count}")
            
            # 发送统计
            cursor.execute('SELECT SUM(send_count) FROM subscribers')
            total_sent = cursor.fetchone()[0] or 0
            report_lines.append(f"  累计发送邮件数: {total_sent}")
            
            # 最近订阅
            cursor.execute('''
                SELECT email, subscribed_at 
                FROM subscribers 
                ORDER BY subscribed_at DESC 
                LIMIT 5
            ''')
            recent_subscribers = cursor.fetchall()
            if recent_subscribers:
                report_lines.append("")
                report_lines.append("  最近订阅:")
                for email, subscribed_at in recent_subscribers:
                    report_lines.append(f"    - {email} ({subscribed_at})")
            
            conn.close()
            
        except Exception as e:
            report_lines.append(f"  数据库查询失败: {str(e)}")
        
        report_lines.append("")
        
        # 4. 文件系统统计
        report_lines.append("## 文件系统统计")
        report_lines.append("")
        
        # 日志文件
        log_files = list(Path(".").glob("*.log"))
        total_log_size = sum(f.stat().st_size for f in log_files)
        report_lines.append(f"  日志文件数: {len(log_files)}")
        report_lines.append(f"  日志总大小: {total_log_size / 1024 / 1024:.2f} MB")
        
        # 缓存文件
        if CACHE_DIR.exists():
            cache_files = list(CACHE_DIR.glob("*.cache"))
            total_cache_size = sum(f.stat().st_size for f in cache_files)
            report_lines.append(f"  缓存文件数: {len(cache_files)}")
            report_lines.append(f"  缓存总大小: {total_cache_size / 1024 / 1024:.2f} MB")
        else:
            report_lines.append("  缓存目录: 不存在")
        
        # 摘要文件
        digest_dir = Path("digests")
        if digest_dir.exists():
            digest_files = list(digest_dir.glob("digest_*.md"))
            report_lines.append(f"  摘要文件数: {len(digest_files)}")
        else:
            report_lines.append("  摘要目录: 不存在")
        
        # 备份文件
        backup_dir = Path("backups")
        if backup_dir.exists():
            backup_files = list(backup_dir.glob("*.db"))
            total_backup_size = sum(f.stat().st_size for f in backup_files)
            report_lines.append(f"  备份文件数: {len(backup_files)}")
            report_lines.append(f"  备份总大小: {total_backup_size / 1024 / 1024:.2f} MB")
        else:
            report_lines.append("  备份目录: 不存在")
        
        report_lines.append("")
        
        # 5. 最近运行记录（如果有日志的话）
        report_lines.append("## 最近运行记录")
        report_lines.append("")
        
        try:
            log_file = Path(LOG_FILE)
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    last_lines = lines[-20:] if len(lines) > 20 else lines
                    
                report_lines.append("  最近20条日志:")
                for line in last_lines:
                    report_lines.append(f"    {line.strip()}")
            else:
                report_lines.append("  日志文件不存在")
        except Exception as e:
            report_lines.append(f"  读取日志失败: {str(e)}")
        
        report_lines.append("")
        report_lines.append("=" * 70)
        
        # 生成报告
        report = "\n".join(report_lines)
        
        # 输出到控制台
        print("\n" + report + "\n")
        
        # 保存到文件
        report_file = Path("system_report.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"运行报告已生成: {report_file}")
        
        return report
        
    except Exception as e:
        logger.error(f"生成报告失败: {str(e)}")
        return ""


# ==================== 更多未实现的TODO函数 ====================

def validate_email_format(email: str) -> bool:
    """
    验证邮箱格式
    TODO: 需要实现更严格的邮箱验证
    """
    pass


def send_test_notification():
    """
    发送测试通知
    TODO: 实现多渠道通知（邮件、短信、webhook）
    """
    pass


def export_subscribers_to_csv():
    """
    导出订阅者到CSV
    TODO: 支持导出为多种格式（CSV、Excel、JSON）
    """
    pass


def import_subscribers_from_csv(csv_file: str):
    """
    从CSV导入订阅者
    TODO: 支持批量导入，带进度显示
    """
    pass


def analyze_article_sentiment():
    """
    分析文章情感
    TODO: 使用NLP模型分析文章情感倾向
    """
    pass


def detect_duplicate_articles():
    """
    检测重复文章
    TODO: 使用文本相似度算法去重
    """
    pass


def generate_reading_statistics():
    """
    生成阅读统计
    TODO: 统计邮件打开率、点击率等
    """
    pass


def schedule_daily_task():
    """
    调度每日任务
    TODO: 使用cron或APScheduler实现定时任务
    """
    pass


def implement_rate_limiter():
    """
    实现速率限制
    TODO: 防止API调用过于频繁
    """
    pass


def add_webhook_support():
    """
    添加Webhook支持
    TODO: 支持将摘要推送到第三方服务
    """
    pass


def create_web_dashboard():
    """
    创建Web管理面板
    TODO: 使用Flask/FastAPI创建管理界面
    """
    pass


def implement_user_preferences():
    """
    实现用户偏好设置
    TODO: 允许用户自定义接收时间、内容类型等
    """
    pass


def add_multi_language_support():
    """
    添加多语言支持
    TODO: 支持英文、日文等多语言摘要
    """
    pass


def implement_content_filtering():
    """
    实现内容过滤
    TODO: 根据关键词、类别过滤内容
    """
    pass


def optimize_llm_prompt():
    """
    优化LLM提示词
    TODO: 使用prompt engineering提升摘要质量
    """
    pass


def add_image_extraction():
    """
    添加图片提取功能
    TODO: 提取文章配图并包含在邮件中
    """
    pass


def implement_retry_mechanism():
    """
    实现重试机制
    TODO: 失败时自动重试，使用指数退避
    """
    pass


def add_health_check_endpoint():
    """
    添加健康检查端点
    TODO: 提供HTTP端点检查系统状态
    """
    pass


def implement_distributed_crawling():
    """
    实现分布式爬取
    TODO: 使用Celery或RQ实现任务队列
    """
    pass


def add_data_visualization():
    """
    添加数据可视化
    TODO: 生成订阅者增长、邮件发送等图表
    """
    pass


def implement_ab_testing():
    """
    实现A/B测试
    TODO: 测试不同的邮件模板、摘要风格
    """
    pass


def add_recommendation_system():
    """
    添加推荐系统
    TODO: 根据用户阅读历史推荐相关文章
    """
    pass


def implement_automatic_categorization():
    """
    实现自动分类
    TODO: 使用机器学习对文章自动分类
    """
    pass


def add_search_functionality():
    """
    添加搜索功能
    TODO: 支持全文搜索历史摘要
    """
    pass


def implement_collaborative_filtering():
    """
    实现协同过滤
    TODO: 基于其他用户推荐内容
    """
    pass


def add_mobile_app_api():
    """
    添加移动应用API
    TODO: 提供RESTful API供移动端调用
    """
    pass


def implement_cost_tracking():
    """
    实现成本追踪
    TODO: 追踪API调用成本和优化
    """
    pass


def add_gdpr_compliance():
    """
    添加GDPR合规功能
    TODO: 实现数据删除、导出等隐私功能
    """
    pass


def implement_content_translation():
    """
    实现内容翻译
    TODO: 自动翻译为其他语言
    """
    pass


def add_audio_summary():
    """
    添加语音摘要
    TODO: 使用TTS生成语音版摘要
    """
    pass

# TODO: 需要重构的内容
# 1. 将爬虫、LLM调用、邮件发送、数据库操作分离到不同模块
# 2. 使用配置文件管理所有配置项
# 3. 添加单元测试
# 4. 改进错误处理
# 5. 使用ORM替代直接SQL操作
# 6. 添加日志轮转
# 7. 实现缓存机制
# 8. 添加性能监控
# 9. 优化API调用频率
# 10. 添加命令行参数解析（使用argparse）
# 11. 实现异步处理提高效率
# 12. 添加任务队列机制
# 13. 完善文档和注释
# 14. 代码格式化和类型提示
# 15. 添加CI/CD配置