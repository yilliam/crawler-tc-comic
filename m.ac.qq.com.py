#!/usr/bin/env python
# encoding=utf-8
from __future__ import absolute_import

__author__ = "Aaron Wu<yilliam@163.com>"

import sys
default_encoding = 'utf-8'
if sys.getdefaultencoding() != default_encoding:
    reload(sys)
    sys.setdefaultencoding(default_encoding)

import logging
import logging.config
import requests
import os
import re
import random
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fpdf import FPDF
import glob

BASE_URL = "http://m.ac.qq.com"
LIST_URL = '/comic/chapterList/id/'
CID = 505430
BASE_FOLDER = "I:/comic"
START = 1
END = 999


def download_page(url):
    logger.info("Download page: %s" % url)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.80 Safari/537.36'
    }
    try:
        data = requests.get(url, headers=headers).content
    except Exception, e:
        logger.exception("%s for %s" % (e, url))
        data = None
    return data


def get_active_page(url, selector=".comic-pic-list-all ul.comic-pic-list"):
    html = None
    logger.info("Download active page: %s \n css selector is %s" % (url, selector))
    driver = webdriver.PhantomJS(executable_path='D:/Python27/Scripts/phantomjs.exe')
    driver.get(url)
    try:
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        html = driver.execute_script("return document.documentElement.outerHTML")
    except Exception, e:
        logger.exception("%s for %s" % (e, url))
    finally:
        driver.quit()
    return html


def get_chapter_list(html):
    title = ""
    chapter_list = []

    if html is None:
        return title, chapter_list

    soup = BeautifulSoup(html, "html.parser")
    title_soup = soup.find('h1', attrs={'class': 'top-title'})
    title = sanitize_name(title_soup.getText())
    chapter_list_soup = soup.find('ul', attrs={'class': 'chapter-list'})

    for chapter_li in chapter_list_soup.find_all('li'):
        detail = chapter_li.find('a', attrs={'class': 'chapter-link'})
        chapter_name = detail.getText()
        chapter_link = detail['href']
        chapter_list.append({"name": chapter_name, "link": chapter_link})

    return title, chapter_list


def get_pictures(html):
    pic_list = []

    if html is None:
        return pic_list

    soup = BeautifulSoup(html, "html.parser")
    pic_list_soup = soup.find('ul', attrs={'class': 'comic-pic-list'})

    for pic_li in pic_list_soup.find_all('li'):
        seq = pic_li['data-index']
        link = pic_li.find('img', attrs={'class': 'comic-pic'})['data-src']

        pic_list.append({"seq": seq, "link": link})

    return pic_list


def save_pic(url, file_name):
    # print "INFO - Save picture： %s as %s" % (url, file_name)
    if os.path.isfile(file_name):
        return True

    try:
        content = requests.get(url).content
    except Exception, e:
        logger.error("Save %s as %s error: %s" % (url, file_name, e))
        time.sleep(3 + random.randint(1, 7))
        return False

    with open(file_name, 'wb') as f:
        f.write(content)

    return True


def sanitize_name(name):
    logger.info("Sanitize name: %s" % name)
    invalid_chars = re.escape('\/:*?"<>|')
    return re.sub(r'[' + invalid_chars + ']', '_', name)


def input_cid():
    cid = raw_input("Please input the id of comic (default is 505430):\n >")
    if not cid:
        logger.info("Using default CID.")
        return CID
    elif cid.isdigit():
        return int(cid)
    else:
        logger.error("Invalid input.")
        return -1


def input_chapters():
    selected_chapter_list = []
    invalid_chars = r'[^0-9-]*$'

    nid_str = raw_input("Please input the chapters range to download (default is 1-999):\n > ")
    if nid_str:

        found = re.match(invalid_chars, nid_str)
        if found is None:
            nid_list = nid_str.split(",")
            for nid in nid_list:
                if nid.find("-") != -1:
                    selected_chapter_list.extend(convert_range(nid))
                else:
                    selected_chapter_list.extend([nid])
        else:
            logger.error("Invalid input.%r " % found.group())
    else:
        selected_chapter_list = range(START, END)
        nid_str = "%s-%s" % (START, END)
    return selected_chapter_list, nid_str


def convert_range(data, sep="-"):
    data = data.split(sep)
    if len(data) == 2:
        return range(int(data[0]), int(data[1]) + 1)
    else:
        return []


def gen_pdf_by_pics(pic_list, file_fullname, width=85, height=114):
    logger.info("Start gen PDF...")
    pdf = FPDF(orientation='P', unit='mm', format=[width, height])
    for pic in pic_list:
        pdf.add_page()
        pdf.image(pic, x=0, y=0, w=width, h=height)

    pdf.output(file_fullname, "F")


def start_download_comic():
    cid = -1
    while cid == -1:
        cid = input_cid()
    title, chapter_list = get_chapter_list(download_page(BASE_URL + LIST_URL + str(cid)))
    if chapter_list:
        logger.info("Total chapters: %s" % len(chapter_list))
    else:
        logger.warning("No chapter info found!")
        return

    selected_chapter_list = []
    while not selected_chapter_list:
        selected_chapter_list, selected_chapter_string = input_chapters()

    comic_path = BASE_FOLDER + "/" + title
    if not os.path.exists(comic_path):
        try:
            os.mkdir(comic_path)
        except Exception, e:
            logger.exception("%s" % e)
            return

    for chapter in chapter_list:
        if int(chapter["name"]) in selected_chapter_list:
            pic_list = get_pictures(get_active_page(BASE_URL + chapter["link"]))
            pic_folder = comic_path + "/" + chapter["name"].zfill(3)
            if not os.path.exists(pic_folder):
                try:
                    os.mkdir(pic_folder)
                except Exception, e:
                    logger.exception("%s" % e)
                    return
            pre_name = pic_folder + "/" + chapter["name"].zfill(3) + "_"
            for pic in pic_list:
                url = pic["link"]
                fname = pre_name + pic["seq"].zfill(2) + ".jpg"
                rc = save_pic(url, fname)
                retry = 0
                while not rc:
                    rc = save_pic(url, fname)
                    if rc:
                        logger.info("Save %s as %s successful." % (url, fname))
                    retry += 1
                    if retry >= 5:
                        logger.error("Max download retry number exceeded.")
                        break


def start_gen_pdf():
    input_dir = ""
    while input_dir or os.path.isdir(input_dir):
        input_dir = raw_input("请输入已下载漫画的路径(例：I:/comic/海贼王_航海王) \n >")
    pics = []
    selected_chapter_list = []
    selected_chapter_string = "unknown"
    while not selected_chapter_list:
        selected_chapter_list, selected_chapter_string = input_chapters()
    pdf_name = input_dir + "/" + selected_chapter_string.replace(",", "_") + ".pdf"
    logger.info("PDF name will be %s. for %s" % (pdf_name, selected_chapter_list))
    for chapter in selected_chapter_list:
        chapter_path = input_dir + "/" + str(chapter).zfill(3)
        if os.path.isdir(chapter_path):
            pics.extend(glob.glob(chapter_path + "/" + "*.jpg"))
            logger.info("Chapter %s matched." % chapter)
        else:
            logger.warning("Directory not exists. %s" % chapter_path)
    gen_pdf_by_pics(pics, pdf_name)


def main():
    dictLogConfig = {
                    "version":1,
                    "handlers":
                    {
                        "fileHandler":
                        {
                            "class":"logging.FileHandler",
                            "formatter":"basicFormatter",
                            "filename":"m.ac.qq.com.log"
                        },
                        "streamHandler":
                        {
                            "class":"logging.StreamHandler",
                            "formatter":"basicFormatter"
                        }
                    },
                    "loggers":
                    {
                        "m.ac.qq.com":
                        {
                            "handlers":["fileHandler","streamHandler"],
                            "level":"INFO",
                        }
                    }, 
                    "formatters":
                    {
                        "basicFormatter":
                        {
                            "format":"%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                        }
                    }
                }
    global logger
    logging.config.dictConfig(dictLogConfig) 
    logger = logging.getLogger("m.ac.qq.com")
    
    task = 0
    while task not in [1, 2]:
        task = int(raw_input("Which task do you want to conduct? \n 1: Download comic. \n 2: Generate comic PDF\n >"))
    logger.info("Input task is %s" % task)
    if task == 1:
        start_download_comic()
    elif task == 2:
        start_gen_pdf()
    else:
        logger.error("Invalid select!")
        return

    logger.info("Task done!")

if __name__ == '__main__':
    main()
