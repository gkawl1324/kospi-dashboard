#!/usr/bin/env python3
"""
Naver Finance Data Fetcher for KOSPI Dashboard
Fetches real-time stock, index, exchange rate, and oil price data
from Naver Finance and saves as data.json for GitHub Pages dashboard.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://finance.naver.com/'
}

# Stock codes
STOCKS = {
    '005930': 'Samsung Electronics',
    '000660': 'SK Hynix',
    '003550': 'LG',
    '035420': 'NAVER'
}

def clean_number(text):
    """Remove commas and whitespace from number strings"""
    if not text:
        return '0'
    return re.sub(r'[,\s]', '', text.strip())

def get_kospi_data():
    """Fetch KOSPI index data from Naver Finance"""
    print("[INFO] Fetching KOSPI index data...")
    url = 'https://finance.naver.com/sise/sise_index.naver?code=KOSPI'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Current index value
        now_val = soup.select_one('#now_value')
        current = clean_number(now_val.text) if now_val else '0'

        # Change value and percentage
        change_val = soup.select_one('#change_value_and_rate')
        if change_val:
            parts = change_val.text.strip().split()
            change = clean_number(parts[0]) if len(parts) > 0 else '0'
            change_pct = parts[1].strip('()%') if len(parts) > 1 else '0'
        else:
            change = '0'
            change_pct = '0'

        # Determine direction (up/down)
        change_type = soup.select_one('#change_value_and_rate')
        is_up = True
        if change_type:
            parent = change_type.find_parent()
            if parent and ('down' in str(parent.get('class', '')) or 'ndn' in str(parent.get('class', ''))):
                is_up = False

        # Additional info
        quant = soup.select_one('#quant')
        volume = clean_number(quant.text) if quant else '0'

        amount = soup.select_one('#amount')
        trade_amount = clean_number(amount.text) if amount else '0'

        return {
            'name': 'KOSPI',
            'current': current,
            'change': change if is_up else f'-{change}',
            'changePct': change_pct if is_up else f'-{change_pct}',
            'direction': 'up' if is_up else 'down',
            'volume': volume,
            'tradeAmount': trade_amount,
        }
    except Exception as e:
        print(f"[ERROR] Failed to fetch KOSPI data: {e}")
        return None

def get_stock_data(code, name):
    """Fetch individual stock data from Naver Finance"""
    print(f"[INFO] Fetching stock data for {name} ({code})...")
    url = f'https://finance.naver.com/item/main.naver?code={code}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Current price from the today section
        today = soup.select_one('.today')
        current = '0'
        if today:
            em = today.select_one('em span.blind')
            if em:
                current = clean_number(em.text)

        # Korean name
        wrap_company = soup.select_one('.wrap_company h2 a')
        kr_name = wrap_company.text.strip() if wrap_company else name

        # Change info
        no_exday = soup.select_one('.no_exday')
        change = '0'
        change_pct = '0'
        is_up = True

        if no_exday:
            # Check for blind text elements for change value
            blinds = no_exday.select('span.blind')
            if len(blinds) >= 2:
                change = clean_number(blinds[0].text)
                change_pct = clean_number(blinds[1].text).replace('%', '')

            # Check direction
            em_tags = no_exday.select('em')
            for em in em_tags:
                cls = str(em.get('class', ''))
                if 'ndn' in cls or 'down' in cls:
                    is_up = False
                    break

        # Volume and other details from table
        table = soup.select_one('.aside_invest_info table')
        volume = '0'
        market_cap = '0'
        high = '0'
        low = '0'
        open_price = '0'

        if table:
            tds = table.select('td span.blind')
            if len(tds) >= 10:
                prev_close = clean_number(tds[0].text)
                open_price = clean_number(tds[2].text)
                high = clean_number(tds[1].text)
                low = clean_number(tds[5].text)
                volume = clean_number(tds[3].text)
                market_cap = clean_number(tds[6].text)

        return {
            'code': code,
            'name': kr_name,
            'nameEn': name,
            'current': current,
            'change': change if is_up else f'-{change}',
            'changePct': change_pct if is_up else f'-{change_pct}',
            'direction': 'up' if is_up else 'down',
            'volume': volume,
            'high': high,
            'low': low,
            'open': open_price,
            'marketCap': market_cap,
        }
    except Exception as e:
        print(f"[ERROR] Failed to fetch stock data for {code}: {e}")
        return None

def get_exchange_rates():
    """Fetch exchange rate data from Naver Finance Market Index"""
    print("[INFO] Fetching exchange rates...")
    url = 'https://finance.naver.com/marketindex/'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')

        rates = []
        # Exchange rate items
        exchange_items = soup.select('#exchangeList li')
        for item in exchange_items:
            name_tag = item.select_one('.h_lst span.blind')
            if not name_tag:
                continue
            name = name_tag.text.strip()

            value_tag = item.select_one('.value')
            value = clean_number(value_tag.text) if value_tag else '0'

            change_tag = item.select_one('.change')
            change = clean_number(change_tag.text) if change_tag else '0'

            # Direction
            blind_tags = item.select('.blind')
            direction = 'up'
            for bt in blind_tags:
                if bt.text.strip() in ['íë½', 'ë³´í©']:
                    direction = 'down' if bt.text.strip() == 'íë½' else 'flat'

            # Map to currency pair
            pair = ''
            if 'USD' in name or 'ë¯¸êµ­' in name or 'ë¬ë¬' in name:
                pair = 'USD/KRW'
            elif 'EUR' in name or 'ì ë½' in name or 'ì ë¡' in name:
                pair = 'EUR/KRW'
            elif 'JPY' in name or 'ì¼ë³¸' in name or 'ì' in name:
                pair = 'JPY/KRW'
            elif 'GBP' in name or 'ìêµ­' in name or 'íì´ë' in name:
                pair = 'GBP/KRW'
            elif 'CNY' in name or 'ì¤êµ­' in name or 'ìì' in name:
                pair = 'CNY/KRW'

            if pair:
                rates.append({
                    'pair': pair,
                    'name': name,
                    'value': value,
                    'change': change,
                    'direction': direction,
                })

        return rates
    except Exception as e:
        print(f"[ERROR] Failed to fetch exchange rates: {e}")
        return []

def get_oil_prices():
    """Fetch oil price data from Naver Finance"""
    print("[INFO] Fetching oil prices...")
    oils = []

    # WTI
    oil_codes = {
        'OIL_CL': {'name': 'WTI', 'unit': 'USD/barrel'},
        'OIL_BRT': {'name': 'Brent', 'unit': 'USD/barrel'},
        'OIL_DU': {'name': 'Dubai', 'unit': 'USD/barrel'},
    }

    for code, info in oil_codes.items():
        try:
            url = f'https://finance.naver.com/marketindex/commodityDetail.naver?marketindexCd={code}'
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = 'euc-kr'
            soup = BeautifulSoup(resp.text, 'html.parser')

            value_tag = soup.select_one('.no_today .no_down em, .no_today .no_up em, .no_today em')
            if value_tag:
                blinds = value_tag.select('span.blind')
                value = clean_number(blinds[0].text) if blinds else clean_number(value_tag.text)
            else:
                value = '0'

            change_tag = soup.select_one('.no_exday em span.blind')
            change = clean_number(change_tag.text) if change_tag else '0'

            direction = 'up'
            no_exday = soup.select_one('.no_exday .ico')
            if no_exday:
                if 'down' in str(no_exday.get('class', '')) or 'íë½' in no_exday.text:
                    direction = 'down'

            oils.append({
                'code': code,
                'name': info['name'],
                'value': value,
                'change': change,
                'direction': direction,
                'unit': info['unit'],
            })
            print(f"  [OK] {info['name']}: {value}")
        except Exception as e:
            print(f"  [ERROR] Failed to fetch {info['name']}: {e}")
            oils.append({
                'code': code,
                'name': info['name'],
                'value': '0',
                'change': '0',
                'direction': 'flat',
                'unit': info['unit'],
            })

    # Gold price
    try:
        url = 'https://finance.naver.com/marketindex/goldDetail.naver'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')

        value_tag = soup.select_one('.no_today em')
        if value_tag:
            blinds = value_tag.select('span.blind')
            gold_value = clean_number(blinds[0].text) if blinds else clean_number(value_tag.text)
        else:
            gold_value = '0'

        change_tag = soup.select_one('.no_exday em span.blind')
        gold_change = clean_number(change_tag.text) if change_tag else '0'

        oils.append({
            'code': 'GOLD',
            'name': 'Gold',
            'value': gold_value,
            'change': gold_change,
            'direction': 'up',
            'unit': 'KRW/g',
        })
        print(f"  [OK] Gold: {gold_value}")
    except Exception as e:
        print(f"  [ERROR] Failed to fetch gold price: {e}")

    return oils

def get_news_headlines():
    """Fetch latest financial news headlines from Naver Finance"""
    print("[INFO] Fetching financial news...")
    url = 'https://finance.naver.com/news/mainnews.naver'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')

        headlines = []
        news_items = soup.select('.mainNewsList li')[:8]
        for item in news_items:
            a_tag = item.select_one('a')
            if a_tag:
                title = a_tag.text.strip()
                link = a_tag.get('href', '')
                if link and not link.startswith('http'):
                    link = 'https://finance.naver.com' + link
                headlines.append({
                    'title': title,
                    'link': link,
                })

        return headlines
    except Exception as e:
        print(f"[ERROR] Failed to fetch news: {e}")
        return []

def main():
    """Main function to fetch all data and save as JSON"""
    print("=" * 60)
    print(f"  KOSPI Dashboard Data Fetcher")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    data = {
        'lastUpdated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date': datetime.now().strftime('%Y.%m.%d'),
        'kospi': None,
        'stocks': [],
        'exchangeRates': [],
        'oilPrices': [],
        'news': [],
    }

    # 1. Fetch KOSPI index
    kospi = get_kospi_data()
    if kospi:
        data['kospi'] = kospi
        print(f"  [OK] KOSPI: {kospi['current']}")

    # 2. Fetch individual stocks
    for code, name in STOCKS.items():
        stock = get_stock_data(code, name)
        if stock:
            data['stocks'].append(stock)
            print(f"  [OK] {stock['name']}: {stock['current']}")

    # 3. Fetch exchange rates
    rates = get_exchange_rates()
    data['exchangeRates'] = rates
    print(f"  [OK] Exchange rates: {len(rates)} pairs")

    # 4. Fetch oil prices
    oils = get_oil_prices()
    data['oilPrices'] = oils
    print(f"  [OK] Oil prices: {len(oils)} items")

    # 5. Fetch news
    news = get_news_headlines()
    data['news'] = news
    print(f"  [OK] News: {len(news)} headlines")

    # Save to data.json
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Data saved to {output_path}")
    print(f"  KOSPI: {data['kospi']['current'] if data['kospi'] else 'N/A'}")
    print(f"  Stocks: {len(data['stocks'])} items")
    print(f"  Exchange rates: {len(data['exchangeRates'])} pairs")
    print(f"  Oil prices: {len(data['oilPrices'])} items")
    print(f"  News: {len(data['news'])} headlines")

if __name__ == '__main__':
    main()
