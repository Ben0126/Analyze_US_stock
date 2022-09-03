# -*- coding: utf-8 -*-
"""
Created on Tue Aug 23 12:08:04 2022

@author: SPY
"""

import pandas as pd
import urllib
import urllib.request
import requests as re
from bs4 import BeautifulSoup
import yfinance as yf
from pytrends.request import TrendReq
import datetime as dt
import time
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import requests
import warnings

url = 'https://www.slickcharts.com/sp500'
headers = {"User-Agent" : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36'}
warnings.filterwarnings('ignore')


try:
    request = requests.get(url, headers = headers)
    data = pd.read_html(request.text)[0]
    stk_list = data.Symbol
    stk_list = data.Symbol.apply(lambda x: x.replace('.', '-'))[:510]
    stk_list
except:
    print('ERROR 001')  
    
    
"""
公司基本資料與價量資料
抓取最後90天交易資料
"""
try:
    stock = yf.Ticker('AAPL')
    stk_basic_data = stock.info
    info_columns = list(stk_basic_data.keys())
    # stk_info_df 存放基本資料
    stk_info_df = pd.DataFrame(index = stk_list.sort_values(), columns = info_columns)
    # stk_price_df 存放價量資料
    stk_price_df = pd.DataFrame(columns = ['label','Open','High','Low','Close','Adj Close','Volume'])
    
    for i in stk_list:
        try:
            #print('processing: ' + i)
            stock = yf.Ticker(i)
            info_dict = stock.info
            columns_included = list(info_dict.keys())
            stk_info_df.loc[i,columns_included] = list(info_dict.values())
            temp = yf.download(i, start = dt.datetime.today() + dt.timedelta(-270))
            temp['label'] = i
            temp = temp.iloc[-90:,:]
            stk_price_df = stk_price_df.append(temp)
            time.sleep(0.5)
        except:
            print("ERROR: can't get " + i +"'s trand data")
            continue
 

    """  
    資料包含：股票名稱 / 種類 / 最後股息值 / 殖利率 / 本益比 / 近四季每股盈餘
        最後收盤價 / 52週最高及最低點 / 50天平均 / 52週漲跌幅  / 200天平均 / beta
    """
    stk_info_df = stk_info_df[['longName','sector','lastDividendValue','dividendYield','pegRatio','trailingEps'
                               ,'regularMarketPrice','fiftyTwoWeekHigh','fiftyTwoWeekLow','fiftyDayAverage'
                               ,'52WeekChange','twoHundredDayAverage','beta']]

    
    stk_price_df['Date'] = list(map(lambda x: dt.datetime.strftime(x, '%Y-%m-%d'), list(stk_price_df.index)))
    stk_price_df = stk_price_df[['label','Date','Open','High','Low','Close','Adj Close','Volume']]
except:
    print('ERROR 002') 
    

"""
stk_info_df ，上傳到 Google 試算表 - 股票基本資料
stk_price_df ，上傳到Google 試算表 - 股票價量資料
"""
try:
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name('my-usstock-information-center-27603531a116.json', scope)
    gc = gspread.authorize(credentials)
    sh = gc.open('我的投資情報專頁')
    
    ws = sh.worksheet('股票基本資料')
    set_with_dataframe(ws, stk_info_df, row = 1, col = 1, include_index = True, include_column_header = True)

    ws = sh.worksheet('股票價量資料')
    set_with_dataframe(ws, stk_price_df, row = 1, col = 1, include_index = False, include_column_header = True)
except:
    print('ERROR 003')


# Google 搜尋量資料
pytrends = TrendReq(hl = 'en-US', tz = 360)
# trend_df 存放 Google搜尋指數資料
trend_df = pd.DataFrame(columns = stk_list)

for stk in stk_list:
    try:
        #print('processing : ' + stk)
        kw_list = [stk]
        pytrends.build_payload(kw_list, timeframe = 'today 3-m')
        trend_df[stk] = pytrends.interest_over_time()[stk]
        time.sleep(1)
    except:
        print("ERROR: can't get " + stk + "'s google trends data")
        continue

trend_df.index = list(map(lambda x: dt.datetime.strftime(x, '%Y-%m-%d'), list(trend_df.index)))

# trend_df 所有股票 Google搜尋指數資料，上傳到Google 試算表 - 股票搜尋度指數

try:
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name('my-usstock-information-center-27603531a116.json', scope)
    gc = gspread.authorize(credentials)
    sh = gc.open('我的投資情報專頁')

    ws = sh.worksheet('股票搜尋度指數')
    set_with_dataframe(ws, trend_df, row = 1, col = 1, include_index = True, include_column_header = True)
except:
    print("ERROR 004")


# 投資大師持股
# 由於每一檔股票，投資大師的數量都不一，因此先創一個空的 result 容器，後續迴圈的過程中，再把資料逐筆用 append 的方式紀錄
result = []
for j in stk_list:
    try:
        # 針對 BRK-B 這檔股票，Gurufocus 網站的代碼辨認是 BRK.B
        if j == 'BRK-B':
            j = 'BRK.B'
        print('processing: ' + j)
        soup = BeautifulSoup(re.get("https://www.gurufocus.com/stock/" + j + "/guru-trades").text, "html5lib")
        
        i=[0,12]
        #num = soup.find()
        for i in range(0,12):
            nav = soup.find(id = i)
            h = nav.parent

            # 每一筆資料都用 dictionary 紀錄
            data = {'stk': None,
                    'investor': None,
                    'port_date': None,
                    'current_share': None,
                    'per_outstand': None,
                    'per_total_asset': None,
                    'comment': None}

            data['stk'] = j
            data['investor'] = h.find_all('tr')[i].find_all('td')[0].get_text().replace('\n','')
            data['port_date'] = h.find_all('tr')[i].find_all('td')[1].get_text()
            data['current_share'] = h.find_all('tr')[i].find_all('td')[2].get_text()
            data['per_outstand'] =h.find_all('tr')[i].find_all('td')[3].get_text()
            data['per_total_asset'] = h.find_all('tr')[i].find_all('td')[4].get_text()
            data['comment'] = h.find_all('tr')[i].find_all('td')[5].get_text()
            # 填滿這筆紀錄的所有內容後，append 到 result 容器中
            result.append(data)
    except:
        print("ERROR: no " + j + "'s investment leader data")
        continue
    
    
big_trader_df = pd.DataFrame.from_dict(result)
big_trader_df = big_trader_df[list(big_trader_df.columns)[-1:] + list(big_trader_df.columns)[:-1]]


scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('my-usstock-information-center-27603531a116.json', scope)
gc = gspread.authorize(credentials)
sh = gc.open('我的投資情報專頁')

# 把 big_trader_df 所有投資大師持股狀況資料，上傳到 知名投資大師的持股資料
ws = sh.worksheet('知名投資大師的持股資料')
set_with_dataframe(ws, big_trader_df, row = 1, col = 1, include_index = False, include_column_header = True)


# 重大經濟事件
url = 'https://hk.investing.com/economic-calendar/'
r = urllib.request.Request(url)
r.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36')
response = urllib.request.urlopen(r)
soup = BeautifulSoup(response.read(), 'html.parser')

# 從 html 編碼中找出目標表格！
table = soup.find('table', {'id': 'economicCalendarData'})
content = table.find('tbody').findAll('tr', {'class': 'js-event-item'})

# 如同爬取投資大師持股資料的作法將資料紀錄在 dictionary，然後 append 在 result
result = []
for i in content:
    news = {'time': None,
            'country': None,
            'impact': None,
            'event': None,
            'actual': None,
            'forecast': None,
            'previous': None}

    news['time'] = i.attrs['data-event-datetime']
    news['country'] = i.find('td', {'class': 'flagCur'}).find('span').get('title')
    news['impact'] = i.find('td', {'class': 'sentiment'}).get('title')
    news['event'] = i.find('td', {'class': 'event'}).find('a').text.strip()
    news['actual'] = i.find('td', {'class': 'bold'}).text.strip()
    news['forecast'] = i.find('td', {'class': 'fore'}).text.strip()
    news['previous'] = i.find('td', {'class': 'prev'}).text.strip()
    result.append(news)

# 同樣地使用 .from_dict 將 result 轉換成 DataFrame
event_df = pd.DataFrame.from_dict(result)
event_df = event_df[list(event_df.columns)[-1:] + list(event_df.columns)[:-1]]
event_df


scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('my-usstock-information-center-27603531a116.json', scope)
gc = gspread.authorize(credentials)
sh = gc.open('我的投資情報專頁')

# 把 event_df 今日重大經濟事件簿，上傳到 經濟事件簿資料

ws = sh.worksheet('經濟事件簿資料')
set_with_dataframe(ws, event_df, row = 1, col = 2, include_index = False, include_column_header = True)