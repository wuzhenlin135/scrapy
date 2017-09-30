#!/usr/bin/env python
#  -*- coding:utf-8 -*-

"""
@author: ben
@time: 4/11/17
@desc: 
"""

import scrapy
import logging
import json
import time
import MySQLdb

from ..items import NovelItem
from ..items import ChaptersItem
from .. import settings

from ..utils.UrlParse import get_domain
from ..utils.Constant import Constant


class NovelSpider(scrapy.Spider):
    def __init__(self, *args, **kwargs):
        dbparams = dict(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            db=settings.MYSQL_DATABASE,
            user=settings.MYSQL_USER,
            passwd=settings.MYSQL_PASSWORD,
            charset='utf8',
            use_unicode=False
        )
        logging.info('#####NovelSpider:__init__():dbparams info : {0}'.format(dbparams))

        self.conn = MySQLdb.connect(**dbparams)

        super(NovelSpider, self).__init__(*args, **kwargs)

    name = 'novel'
    allowed_domains = settings.ALLOWED_DOMAINS
    start_urls = settings.START_URLS

    def parse(self, response):
        logging.info('#####NovelSpider:parse()#####')

        novelitem = NovelItem()

        content = response.xpath("//div[@class='content']/div")

        novelitem['picture'] = content[0].xpath("//div[@class='imgShow']/img/@src").extract()[0]
        novelitem['name'] = content[0].xpath("//div[@class='tit']/h1/text()").extract()[0].strip()
        novelitem['status'] = content[0].xpath("//div[@class='tit']/span/text()").extract()[0].strip()
        novelitem['author'] = content[0].xpath("//div[@class='author']//a/text()").extract()[0].strip()
        novelitem['author_href'] = 'http://book.easou.com' + content[0].xpath("//div[@class='author']//a/@href").extract()[0]
        novelitem['type'] = content[0].xpath("//div[@class='kind']//a/text()").extract()[0].strip()
        novelitem['type_href'] = 'http://book.easou.com' + content[0].xpath("//div[@class='kind']//a/@href").extract()[0]
        novelitem['update_time'] = content[0].xpath("//div[@class='updateDate']/span/text()").extract()[0]
        novelitem['source'] = content[0].xpath("//div[@class='source']/span/text()").extract()[0].strip()
        novelitem['description'] = content[0].xpath("//div[@class='desc']/text()").extract()[0].strip()
        novelitem['latest_chapters'] = content[0].xpath("//div[@class='last']/a/text()").extract()[0].strip().split(' ')[1]
        novelitem['chapters_categore_href'] = content[0].xpath("//div[@class='allcategore']//a/@href").extract()[0]

        logging.info('#####NovelSpider:parse():novelitem info:{0}#####'.format(novelitem))

        yield scrapy.Request('http://book.easou.com' + novelitem['chapters_categore_href'], method='GET',
                             callback=self.get_page_urls, meta={'novel_detail': novelitem})

    def get_page_urls(self, response):
        logging.info('#####NovelSpider:get_page_urls():response info:{0}#####'.format(response))

        one_page_url = response.url

        # 通过<a>标签判断是否有多页，只有一页时<a>标签为0
        a_selector = response.xpath("//div[@class='wrap']/a")
        page_urls = []
        if not a_selector:
            page_urls.append(response.url)
        else:
            # 获取倒数第二个<a>标签的文本内容，此数据为总共的页数
            total_pages = a_selector[-2].xpath('span/text()').extract()[0].strip()
            one_page_urls = one_page_url.split('/')
            for i in xrange(1, int(total_pages)+1):
                last_url = str(i) + one_page_urls.pop(-1)[1:]
                one_page_urls.append(last_url)
                com_url = '/'.join(one_page_urls)
                page_urls.append(com_url)

        logging.info('#####NovelSpider:get_page_urls():page_urls info:{0}#####'.format(page_urls))

        for page_url in page_urls:
            yield scrapy.Request(page_url, method='GET', callback=self.chapters_categore,
                                 meta={'novel_detail': response.meta['novel_detail']}, dont_filter=True)

    def chapters_categore(self, response):
        logging.info('#####NovelSpider:chapters_categore():response info:{0}#####'.format(response))

        categores_hrefs = response.xpath("//div[@class='category']/ul//a/@href").extract()
        logging.info('#####NovelSpider:chapters_categore():categores_hrefs info:{0}#####'.format(categores_hrefs))
        cur_page = int(response.xpath("//div[@class='wrap']/span[@class='cur']/text()").extract()[0].strip())
        logging.info('#####NovelSpider:chapters_categore():cur_page info:{0}#####'.format(cur_page))

        novel_detail = response.meta['novel_detail']

        cur = self.conn.cursor()

        query_resid_sql = "select res_id from novel_chapters where novel_detail_id = " \
                          "(select id from novel_detail where name=%s and author=%s)"
        params = (novel_detail['name'], novel_detail['author'])

        cur.execute(query_resid_sql, params)
        res = cur.fetchall()
        logging.info('#####NovelSpider:chapters_categore():res info:{0}#####'.format(res))
        if res:
            # 上一次爬取小说章节可能由于多种原因导致没有爬取下来，接下来每次爬取最新章节时重复爬取没有入库的章节
            res_ids = [res_id[0] for res_id in res]
            categores_hrefs = [(i, categores_hrefs[i-999*(cur_page-1)-1]) for i in xrange(999*(cur_page-1)+1, self.get_chapter_index(categores_hrefs[-1])+1) if i not in res_ids]
            for index, c_item in categores_hrefs:
                yield scrapy.Request('http://book.easou.com' + c_item, callback=self.chapters_detail,
                                     meta={'novel_detail': novel_detail, 'chapter_id': index})
        else:
            for c_item in categores_hrefs:
                yield scrapy.Request('http://book.easou.com' + c_item, callback=self.chapters_detail,
                                     meta={'novel_detail': novel_detail, 'chapter_id': self.get_chapter_index(c_item)})
        cur.close()
        # self.conn.commit()
        # self.conn.close()

    def get_chapter_index(self, url):
        if not url:
            return None
        return int(url.split('/').pop(-1).split('.').pop(0))

    def chapters_detail(self, response):
        logging.info('#####NovelSpider:chapters_detail():response info:{0}#####'.format(response))

        novel_item = response.meta['novel_detail']
        chapter_id = int(response.meta['chapter_id'])

        chapter_item = ChaptersItem()
        chapter_item['source'] = response.url
        chapter_item['res_id'] = chapter_id

        source_domain = get_domain(chapter_item['source'])
        logging.info('#####NovelSpider:chapters_detail():source_domain info:{0}#####'.format(source_domain))
        if not source_domain:
            logging.error("#####NovelSpider:chapters_detail():爬取数据链接出错,请检查小说章节详情链接:{0}".format(chapter_item['source']))
            return

        if source_domain == Constant.SOURCE_DOMAIN['DUXS']:
            chapter_item['name'] = response.xpath("//div[@class='content']//h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@class='chapter-content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['ASZW']:
            chapter_item['name'] = response.xpath("//div[@class='bdb']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='contents']/text()").extract()[0].strip())
        elif source_domain == Constant.SOURCE_DOMAIN['BQG']:
            chapter_item['name'] = response.xpath("//div[@class='bookname']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['BQW']:
            chapter_item['name'] = response.xpath("//div[@class='read_title']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@class='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['ZW']:
            chapter_item['name'] = response.xpath("//div[@class='bdsub']//dd[0]/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@class='bdsub']//dd[@id='contents']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['GLW']:
            pass
        elif source_domain == Constant.SOURCE_DOMAIN['SW']:
            chapter_item['name'] = response.xpath("//div[@class='bookname']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@class='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['QL']:
            chapter_item['name'] = response.xpath("//div[@class='bookname']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['XS']:
            chapter_item['name'] = response.xpath("//div[@class='wrapper_main']/h1/span[@id='htmltimu']/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='BookText']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['MPZW']:
            chapter_item['name'] = response.xpath("//div[@class='P_Left']//h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='clickeye_content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['WXG']:
            chapter_item['name'] = response.xpath("//div[@class='content']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['ZDD']:
            chapter_item['name'] = response.xpath("//div[@id='a_main']//h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//dd[@id='contents']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['ASZWO']:
            chapter_item['name'] = response.xpath("//div[@class='bdb']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='contents']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['KK']:
            chapter_item['name'] = response.xpath("//h1[@id='title']/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['IF']:
            chapter_item['name'] = response.xpath("//div[@id='wrap']//h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['KZW']:
            chapter_item['name'] = response.xpath("//div[@class='bookname']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['YBDU']:
            chapter_item['name'] = response.xpath("//div[@class='h1title']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='htmlContent']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['JZW']:
            chapter_item['name'] = response.xpath("//div[@class='bookname']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['DJD']:
            chapter_item['name'] = response.xpath("//div[@id='title']/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content1']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['KW']:
            chapter_item['name'] = response.xpath("//div[@class='chapter_title']/h2/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='inner']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['RW']:
            chapter_item['name'] = response.xpath("//div[@class='bookname']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['TTSB']:
            chapter_item['name'] = response.xpath("//div[@class='zhangjieming']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@class='zhangjieTXT']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['DHZW']:
            chapter_item['name'] = response.xpath("//div[@class='bookname']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='BookText']/node()").extract()).strip()
        elif source_domain == Constant.SOURCE_DOMAIN['58XS']:
            chapter_item['name'] = response.xpath("//div[@class='bookname']/h1/text()").extract()[0].strip()
            chapter_item['content'] = ''.join(response.xpath("//div[@id='content']/node()").extract()).strip()
        else:
            logging.error("#####NovelSpider:chapters_detail():没有此域名网站爬取模板，请联系管理员！:{0}".format(chapter_item['source']))
            return
        yield {'novel_item': novel_item, 'chapter_item': chapter_item}



