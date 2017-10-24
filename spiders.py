from urllib.parse import urlencode
import requests
import pymongo
from lxml.etree import XMLSyntaxError
from pyquery import PyQuery as pq
from config import *
import time

client = pymongo.MongoClient(MONGO_URL,MONGO_PORT)
db = client[MONGO_DB]

base_url = 'http://weixin.sogou.com/weixin?'
headers = {
    'Cookie':'CXID=91F98C944A0EB892DE3221A2098F53B6; ad=fZllllllll2BimZJlllllVXuEl6lllllKGrTSkllll9lllll9klll5@@@@@@@@@@; SUID=42BEC33C2E08990A00000000584762B7; ABTEST=4|1508727551|v1; IPLOC=CN1100; weixinIndexVisited=1; SUV=009F178C6A78606A59ED5B25B6CF9337; SNUID=414C53412B2E700226BBE2AA2CBC43EF; JSESSIONID=aaaj2qfp4OiJl_XC8sv8v; sct=4; ppinf=5|1508729131|1509938731|dHJ1c3Q6MToxfGNsaWVudGlkOjQ6MjAxN3x1bmlxbmFtZTo5Okx1Y2t5X2JveXxjcnQ6MTA6MTUwODcyOTEzMXxyZWZuaWNrOjk6THVja3lfYm95fHVzZXJpZDo0NDpvOXQybHVQREM1WHBZdnRSUTdrVFFUeEdySFBFQHdlaXhpbi5zb2h1LmNvbXw; pprdig=gy6zdHcNEyrPtBRISqJkjCiAKKFG7qxVggxGoV7lTGkR6k_OVb4c5OKXC4tGhEFwcgON3QKUMtbi7pGpBwjUcN8dBwXCWVS-8av6UuXbTPEydCrzThdSCAWx-pPMkOXq7vuIy2sBFSf55nfINOovOx_MLpPNEPyOT9xdVCvYGo0; sgid=26-31596725-AVntYSriaTXEdcpB5ibicGzccc; ppmdig=15087291310000000ccc8f707d7db17c428d9b9b9e94673e',
    'Host':'weixin.sogou.com',
    'Upgrade-Insecure-Requests':'1',
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'
}


def get_proxy():
    time.sleep(3)
    try:
        response = requests.get(PROXY_POOL_URL)
        if response.status_code == 200:
            print(response.text)
            return response.text
        return None
    except ConnectionError:
        return None

def get_html(url,count=1):
    '''
    获取对应url下的html信息
    1、首先需要拿到Cookie，伪装成登录状态（非登录状态下只能访问10页）
    2、如果我们要访问的页数不存在的话就会跳转302.
    3、如果我们没有拿到当前url的html信息，或者是访问超时，就自己执行自己的代码。
    :param url:
    :return:
    '''
    print('当前URL：{0}'.format(url))
    global proxy
    if count >= MAX_CONUT:
        print('已经到最大请求错误数')
        return None
    try:
        if PROXY:
            proxies = {
                'http':'http://{0}'.format(PROXY)
            }
            response = requests.get(url,allow_redirects=False,headers=headers,proxies=proxies)
        else:
            response = requests.get(url, allow_redirects=False, headers=headers)
        if response.status_code == 200:
            return response.text
        #上面的allow_redirects等于False，证明我们不允许直接跳转到302页面，只获取302这个状态码。
        if response.status_code == 302:
            print('302 Error')
            proxy = get_proxy()
            if proxy:
                print('正在使用代理IP：{0}'.format(proxy))
                return get_html(url)
            else:
                print('获取代理IP地址失败')
                return None
    except ConnectionError as e:
        print('已经到最大请求错误数',e.args)
        proxy = get_proxy()
        count += 1
        return get_html(url,count)

def get_index(keyword,page):
    '''
    获取需要访问的url：
    1、首先需要伪造url，创建好需要提交的url参数。
    2、用get_html方法去访问（取）对应url下的html信息。
    :param keyword:
    :param page:
    :return:
    '''
    data = {
        'query':keyword,
        'type':2,
        'page':page,
        's_from': 'input',
        'ie': 'utf8',
        '_sug_': 'n'
    }
    queries = urlencode(data)
    url = base_url + queries
    html = get_html(url)
    return  html

def parse_index(html):
    '''
    获取没篇文章的url
    :param html:
    :return:
    '''
    doc = pq(html)
    items = doc('.news-box .news-list li .txt-box h3 a').items()
    for item in items:
        yield item.attr('href')

def get_detail(url):
    '''
    测试每篇文章的链接是否可以打开
    :param url:
    :return:
    '''
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except ConnectionError:
        return None

def parse_detail(html):
    '''
    解析每篇文章
    :param html:
    :return:
    '''
    try:
        doc = pq(html)
        title = doc('.rich_media_title').text()
        content = doc('.rich_media_content').text()
        date = doc('#post-date').text()
        nickname = doc('.rich_media_meta_list > #post-user').text()
        wechat = doc('#js_profile_qrcode > div > p:nth-child(3) > span').text()
        return {
            'title':title,
            'content':content,
            'date':date,
            'nickname':nickname,
            'wechat':wechat
        }
    except XMLSyntaxError:
        return None
    except Exception:
        return None

def save_to_monge(data):
    '''
    保存到MongoDB数据库
    :param data:
    :return:
    '''
    if db['articles'].update({'title':data['title']},{'$set':data},True):
        print('Saved to Mongo',data['title'])
    else:
        print('Saved to Mongo Failed',data['title'])

def main():
    '''
    接口
    :return:
    '''
    for page in range(1,101):
        html = get_index(KEYWORD,page)
        if html:
            article_urls = parse_index(html)
            #遍历已经拿到的每篇文章的url
            for article_url in article_urls:
                article_html = get_detail(article_url)
                #如果每篇文章的url都可以正常打开
                if article_html:
                    #解析每篇文章的具体内容
                    article_data = parse_detail(article_html)
                    print(article_data)
                    if article_data:
                        save_to_monge(article_data)


if __name__ == '__main__':
    main()



