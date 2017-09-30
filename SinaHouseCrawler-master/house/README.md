
#SinaHouseCrawler
### 简介
基于scrapy, scrapy-redis实现的一个分布式网络爬虫,爬取了 **[新浪房产](http://data.house.sina.com.cn/sc/search/)** 的楼盘信息及户型图片,实现了数据提取,去重,保存,分页数据的采集,数据的增量爬取,代理的使用,失效代理的清除,useragent的切换,图片的下载等功能,并且common模块中的middlewares等功能可以在其他爬虫需求中重复使用.

---
### 数据展示

**房产数据**
![房产数据](https://raw.githubusercontent.com/Fighting-Toghter/Exercise/master/images/house.png)
---
**户型数据**
![户型数据](https://raw.githubusercontent.com/Fighting-Toghter/Exercise/master/images/hosuelayout.png)
---
**CustomImagesPipeline下载的图片**
![图片](https://raw.githubusercontent.com/Fighting-Toghter/Exercise/master/images/image_store.png)
---
**ThreadImagesPipeline下载的图片**
![图片](https://raw.githubusercontent.com/Fighting-Toghter/Exercise/master/images/images.png)

---
### 功能清单:

1. 'sinahouse.pipelines.MongoPipeline'实现数据持久化到mongodb,'sinahouse.pipelines.MySQLPipeline'实现数据异步写入mysql

2. 'common.middlewares.UserAgentMiddleware','common.middlewares.ProxyMiddleware' 分别实现用户代理UserAgent变换和IP代理变换

3. 'sinahouse.pipelines.ThreadImagesPipeline','sinahouse.pipelines.CustomImagesPipeline'分别是基于多线程将图片下载保存到images文件夹和继承scrapy自带  ImagePipline的实现的图片下载保存到images_store

4. 'scrapy.extensions.statsmailer.StatsMailer'是通过设置settings中的mai等相关参数实现发送爬虫运行状态信息到指定邮件.scrapy.mail中的  MailSender也可以实现发送自定义内容邮件 

5. 通过设置setting中的scrapy-redis的相关参数,实现爬虫的分布式运行,或者单机多进程运行.无redis环境时,可以注释掉相关参数,转化为普通的scrapy爬虫程序  
6. 运行日志保存

---
### 运行环境:
1. 只在Python 2.7测试过,请先安装 requirements.txt 中的模块.
2. MySQLPipeline 用到的表:
```
CREATE TABLE `house` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) DEFAULT NULL,
  `price` varchar(50) DEFAULT NULL,
  `open_date` varchar(50) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `lon_lat` varchar(50) DEFAULT NULL,
  `developer` varchar(50) DEFAULT NULL,
  `property_company` varchar(50) DEFAULT NULL,
  `property_manage_fee` varchar(50) DEFAULT NULL,
  `decoration` varchar(50) DEFAULT NULL,
  `cover_path` varchar(128) DEFAULT NULL,
  `source_id` int(11) DEFAULT NULL,
  `url` varchar(128) DEFAULT NULL,
  `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
)

CREATE TABLE `house_layout` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `house_id` int(11) NOT NULL,
  `name` varchar(50) DEFAULT NULL,
  `area` varchar(20) DEFAULT NULL,
  `img_path` varchar(128) DEFAULT NULL,
  `price` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `house_id_refs_id` (`house_id`)
)
```
---
### 其他说明
LOG_FORMATTER = 'sinahouse.utils.PoliteLogFormatter', 实现raise DropItem()时避免scrapy弹出大量提示信息; 图片保存路径,数据库连接等参数,请根据自己环境设置; 更多相关信息请查阅scrapy以及scrapy-redis文档  
  
---  
### 测试方法： 

```
scrapy parse --spider=sinahouse  -c parse_house -d 5 "http://data.house.sina.com.cn/jx108948?wt_source=search_nr_bt02"
```

查看item是否提取成功，item中**字段意义**，请查看**SinaHouseItem**中的注释。    
---
### 运行方法:    
####单机:
```
  cd SinaHouseCrawler    
  scrapy crawl sinahouse   
```
####分布式:    
 配置好setting中的scrapy-redis的相关参数,在各机器中分别按单机方式启动即可    
  
**爬取目标网站**: [新浪房产](http://data.house.sina.com.cn/sc/search/)
