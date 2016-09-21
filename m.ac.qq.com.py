#!/usr/bin/env python
# encoding=utf-8
from __future__ import absolute_import

__author__ = "Aaron Wu<yilliam@163.com>"

import sys
default_encoding = 'utf-8'
if sys.getdefaultencoding() != default_encoding:
    reload(sys)
    sys.setdefaultencoding(default_encoding)
from argparse import ArgumentParser
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
import progressbar
from PyPDF2 import PdfFileMerger, PdfFileReader

Logger = None
BASE_URL = "http://m.ac.qq.com"
LIST_URL = '/comic/chapterList/id/'
CID = 505430


def download_page(url):
    Logger.info("Download page: %s" % url)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.80 Safari/537.36'
    }
    try:
        data = requests.get(url, headers=headers).content
    except Exception, e:
        Logger.exception("%s for %s" % (e, url))
        data = None
    return data


def get_active_page(url, selector=".comic-pic-list-all ul.comic-pic-list"):
    html = None
    Logger.info("Download active page: <%s> with css selector <%s>" % (url, selector))
    driver = webdriver.PhantomJS(executable_path='D:/Python27/Scripts/phantomjs.exe')
    driver.get(url)
    try:
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        html = driver.execute_script("return document.documentElement.outerHTML")
    except Exception, e:
        Logger.exception("%s for %s" % (e, url))
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
        Logger.error("Save %s as %s error: %s" % (url, file_name, e))
        time.sleep(3 + random.randint(1, 7))
        return False

    with open(file_name, 'wb') as f:
        f.write(content)

    return True


def sanitize_name(name):
    Logger.info("Sanitize name: %s" % name)
    invalid_chars = re.escape('\/:*?"<>|')
    return re.sub(r'[' + invalid_chars + ']', '_', name)


def input_cid(cid_selected=None):
    if cid_selected is not None and cid_selected.isdigit():
        cid = int(cid_selected)
        Logger.info("Comic id is %s" % cid_selected)
    else:
        print u'输入漫画的编号（如505430）：\n'
        cid = raw_input(">")

    if cid.isdigit():
        Logger.info("Comic id is %s" % cid)
        return int(cid)
    else:
        Logger.error("Invalid input.")
        return None


def input_chapters(max_chapter_number=None, chapter_selected_string=None):
    selected_chapter_list = []
    invalid_chars = r'[^0-9-]*$'

    nid_str = chapter_selected_string
    if nid_str:
        pass
    else:
        print u'输入目标章节/话（以,或-分隔，默认为最新章节）\n'
        nid_str = raw_input("> ")

    if nid_str:
        found = re.match(invalid_chars, nid_str)
        if found is None:
            nid_list = nid_str.split(",")
            for nid in nid_list:
                if nid.find("-") != -1:
                    selected_chapter_list.extend(convert_range(nid))
                else:
                    selected_chapter_list.extend([nid])
            if max_chapter_number is not None and isinstance(max_chapter_number, int):
                max_selected = max(selected_chapter_list)
                if max_selected > max_chapter_number:
                    Logger.warn("Chapter number exceed. %s" % max_selected)
                if len(selected_chapter_list) == 1 and max_selected > max_chapter_number:
                    Logger.info("Use max chapter. %s" % max_chapter_number)
                    selected_chapter_list = [max_chapter_number]
                else:
                    Logger.info("Filter chapters.")
                    selected_chapter_list = [item for item in selected_chapter_list if item <= max_chapter_number]
        else:
            Logger.error("Invalid input.%r " % found.group())
    elif max_chapter_number is not None and isinstance(max_chapter_number, int):
        Logger.info("Use max chapter. %s" % max_chapter_number)
        selected_chapter_list.append(max_chapter_number)
        nid_str = "%s" % selected_chapter_list

    return selected_chapter_list, nid_str


def convert_range(data, sep="-"):
    data = data.split(sep)
    if len(data) == 2:
        return range(int(data[0]), int(data[1]) + 1)
    else:
        return []


def gen_pdf_by_pics(pic_list, file_fullname, width=85, height=114):
    pdf = new_pdf(width, height)
    add_page(pdf, pic_list)
    save_pdf(pdf, file_fullname)


def new_pdf(width=85, height=114):
    return FPDF(orientation='P', unit='mm', format=[width, height])


def add_page(pdf, pic_list):
    for pic in pic_list:
        pdf.add_page()
        pdf.image(pic, x=0, y=0, w=pdf.w, h=pdf.h)
    return pdf


def save_pdf(pdf, file_fullname):
    pdf.output(file_fullname, "F")


def merge_pdf(filenames, output_file):
    merger = PdfFileMerger()
    for filename in filenames:
        merger.append(PdfFileReader(file(filename, 'rb')))

    merger.write(output_file)


def start_download_comic(comic_id=None, chapters_selected=None, path_selected=None):
    cid = comic_id
    if cid is not None and cid.isdigit():
        cid = int(cid)
    else:
        Logger.warning("Invalid comic id! %s" % comic_id)
        cid = None

    while cid is None:
        cid = input_cid(comic_id)
    title, chapter_list = get_chapter_list(download_page(BASE_URL + LIST_URL + str(cid)))
    if chapter_list:
        Logger.info("Total chapters: %s" % len(chapter_list))
    else:
        Logger.warning("No chapter info found!")
        return

    selected_chapter_list = []
    while not selected_chapter_list:
        max_chapter_id = max(int(chapter["name"]) for chapter in chapter_list)
        selected_chapter_list, selected_chapter_string = input_chapters(max_chapter_number=max_chapter_id,
                                                                        chapter_selected_string=chapters_selected)

    if path_selected is not None:
        comic_path = path_selected + os.path.sep + title
    else:
        comic_base = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + "comic"
        if not os.path.isdir(comic_base):
            os.mkdir(comic_base)
        comic_path = comic_base + os.path.sep + title

    if not os.path.exists(comic_path):
        try:
            os.mkdir(comic_path)
        except Exception, e:
            Logger.exception("%s" % e)
            return

    selected_chapters = [item for item in chapter_list if int(item["name"]) in selected_chapter_list]
    for chapter in selected_chapters:
        pic_list = get_pictures(get_active_page(BASE_URL + chapter["link"]))
        pic_folder = comic_path + os.path.sep + chapter["name"].zfill(3)
        if not os.path.exists(pic_folder):
            try:
                os.mkdir(pic_folder)
            except Exception, e:
                Logger.exception("%s" % e)
                return
        pre_name = pic_folder + os.path.sep + chapter["name"].zfill(3) + "_"
        for pic in pic_list:
            url = pic["link"]
            fname = pre_name + pic["seq"].zfill(2) + ".jpg"
            rc = save_pic(url, fname)
            retry = 0
            while not rc:
                rc = save_pic(url, fname)
                if rc:
                    Logger.info("Save %s as %s successful." % (url, fname))
                retry += 1
                if retry >= 5:
                    Logger.error("Max download retry number exceeded.")
                    break

    if len(selected_chapter_list) == 1:
        start_gen_pdf(comic_path, str(selected_chapter_list[0]))


def start_gen_pdf(comic_path=None, chapter_selected_string=None):
    input_dir = comic_path
    if input_dir is not None and not os.path.isdir(input_dir):
        input_dir = None
    while input_dir is None:
        print(u'选择漫画图片所在目录：(例: I:/comic/海贼王_航海王) \n')
        input_dir = raw_input('>')
        if input_dir:
            if not os.path.isdir(input_dir):
                input_dir = None
        else:
            input_dir = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + 'comic'
            if os.path.isdir(input_dir):
                dirs = filter(os.path.isdir, glob.glob(input_dir + os.path.sep + "*"))
                dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                input_dir = dirs[0]
            else:
                input_dir = None

    Logger.info("Use path %s" % input_dir)

    selected_chapter_list = []
    selected_chapter_string = "unknown"
    max_chapter = max([name for name in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, name))])
    if chapter_selected_string is not None:
        selected_chapter_list, selected_chapter_string = input_chapters(max_chapter_number=max_chapter,
                                                                        chapter_selected_string=chapter_selected_string)
    while not selected_chapter_list:
        selected_chapter_list, selected_chapter_string = input_chapters()
    pdf_name = input_dir + os.path.sep + selected_chapter_string.replace(",", "_") + ".pdf"
    Logger.info("PDF name will be %s. for %s" % (pdf_name, selected_chapter_list))

    added = False
    bar = progressbar.ProgressBar(max_value=len(selected_chapter_list))
    for idx, chapter in enumerate(selected_chapter_list):
        chapter_path = input_dir + os.path.sep + str(chapter).zfill(3)
        if os.path.isdir(chapter_path):
            pics = glob.glob(chapter_path + os.path.sep + "*.jpg")
            print "\n"
            Logger.info("Chapter %s processing..." % chapter)
            chapter_pdf_name = chapter_path + ".pdf"
            if not os.path.isfile(chapter_pdf_name):
                gen_pdf_by_pics(pics, chapter_pdf_name)
            if added:
                merge_pdf([pdf_name, chapter_pdf_name], pdf_name)
            else:
                added = True
                from shutil import copyfile
                copyfile(chapter_pdf_name, pdf_name)
        else:
            Logger.warning("Directory not exists. %s" % chapter_path)
        bar.update(idx + 1)

    if added:
        Logger.info("PDF save")
    else:
        Logger.warn("PDF not generated. %s" % pdf_name)


def select_task(task_selected=None, comic_selected=None, chapters_selected=None, path_selected=None):
    if task_selected is None or not task_selected.isdigit():
        prompt = u'请选择任务：\n  1.下载漫画图片\n  2.生成漫画PDF文档\n  3.退出\n'
        print prompt
        task = int(raw_input('>'))
    else:
        task = int(task_selected)

    Logger.info("Task number : %s" % task)
    time.sleep(1)
    if task == 1:
        start_download_comic(comic_selected, chapters_selected, path_selected)
    elif task == 2:
        start_gen_pdf(comic_path=path_selected, chapter_selected_string=chapters_selected)
    elif task == 3:
        return False
    else:
        Logger.error("Invalid task number. %s" % task)
        return True if task_selected is None else False

    Logger.info("Task done.")


def main():
    dict_log_config = {
                        "version": 1,
                        "handlers":
                        {
                            "fileHandler":
                            {
                                "class": "logging.FileHandler",
                                "formatter": "basicFormatter",
                                "filename": "m.ac.qq.com.log"
                            },
                            "streamHandler":
                            {
                                "class": "logging.StreamHandler",
                                "formatter": "basicFormatter"
                            }
                        },
                        "loggers":
                        {
                            "m.ac.qq.com":
                            {
                                "handlers": ["fileHandler", "streamHandler"],
                                "level": "INFO",
                            }
                        },
                        "formatters":
                        {
                            "basicFormatter":
                            {
                                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                            }
                        }
                    }
    global Logger
    logging.config.dictConfig(dict_log_config) 
    Logger = logging.getLogger("m.ac.qq.com")

    parser = ArgumentParser()

    # Add more options if you like
    parser.add_argument("-t", "--task",
                        dest="task_selected",
                        default=None,
                        help="task selected to conduct: 1- download, 2- generate PDF")

    parser.add_argument("-C", "--comic",
                        dest="comic_selected",
                        default="505430",
                        help="comic id for m.ac.qq.com")

    parser.add_argument("-c", "--chapters",
                        dest="chapters_selected",
                        default=None,
                        help="target chapter list")

    parser.add_argument("-p", "--path",
                        dest="path_selected",
                        default=None,
                        help="target comic path without title")

    args = parser.parse_args()

    while True:
        rc = select_task(args.task_selected, args.comic_selected, args.chapters_selected, args.path_selected)
        if not rc:
            break


if __name__ == '__main__':
    main()
