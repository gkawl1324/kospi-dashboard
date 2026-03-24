#!/usr/bin/env python3
"""
Naver Finance Data Fetcher for KOSPI Dashboard
Fetches real-time stock, index, exchange rate, oil price, and news data
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

# Stock codes and English names
STOCKS = {
    '005930': 'Samsung Electronics',
    '000660': 'SK Hynix',
    '003550': 'LG',
    '035420': 'NAVER'
}


def clean_number(text):
    """Remove commas, whitespace, and non-numeric chars from number strings"""
    if not text:
        return '0'
    cleaned = re.sub(r'[,\s]', '', text.strip())
    # Remove any remaining non-numeric chars except dots and minus
    cleaned = re.sub(r'[^\d.\-]', '', cleaned)
    return cleaned if cleaned else '0'


def clean_pct(text):
    """Extract numeric percentage value, removing any Korean text"""
    if not text:
        return '0'
    match = re.search(r'[-+]?\d+\.?\d*', text)
    return match.group() if match else '0'


def fetch_page(url):
    """Fetch page with automatic encoding detection"""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.apparent_encoding:
        resp.encoding = resp.apparent_encoding
    try:
        resp.text.encode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        resp.encoding = 'euc-kr'
    return BeautifulSoup(resp.text, 'html.parser')


def get_kospi_data():
    """Fetch KOSPI index data from Naver Finance"""
    print("[INFO] Fetching KOSPI index data...")
    url = 'https://finance.naver.com/sise/sise_index.naver?code=KOSPI'
    try:
        soup = fetch_page(url)

        now_val = soup.select_one('#now_value')
        current = clean_number(now_val.text) if now_val else '0'

        change_val = soup.select_one('#change_value_and_rate')
        change = '0'
        change_pct = '0'
        if change_val:
            full_text = change_val.text.strip()
            numbers = re.findall(r'[\d,.]+', full_text)
            if len(numbers) >= 1:
                change = clean_number(numbers[0])
            if len(numbers) >= 2:
                change_pct = clean_number(numbers[1])

        is_up = True
        if change_val:
            parent = change_val.find_parent()
            parent_str = str(parent.get('class', '')) if parent else ''
            if 'down' in parent_str or 'ndn' in parent_str:
                is_up = False
            if '\ud558\ub77d' in change_val.text:
                is_up = False

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


def get_stock_sise_details(code):
    """Fetch open/high/low/volume from the sise detail page by matching th labels"""
    details = {'open': '0', 'high': '0', 'low': '0', 'volume': '0', 'marketCap': '0'}
    try:
        url = f'https://finance.naver.com/item/sise.naver?code={code}'
        soup = fetch_page(url)

        # Parse by matching th text labels to their adjacent td values
        for th in soup.select('th'):
            th_text = th.get_text(strip=True)
            td = th.find_next_sibling('td')
            if not td:
                continue

            blind = td.select_one('span.blind')
            raw_text = blind.text if blind else td.get_text(strip=True)
            val = clean_number(raw_text)

            if val == '0' or not val:
                continue

            if th_text == '\uc2dc\uac00':      # open price
                details['open'] = val
            elif th_text == '\uace0\uac00':    # high price
                details['high'] = val
            elif th_text == '\uc800\uac00':    # low price
                details['low'] = val
            elif th_text == '\uac70\ub798\ub7c9':  # volume
                details['volume'] = val
            elif '\uc2dc\uac00\uce1d\uc561' in th_text:  # market cap
                details['marketCap'] = val

        print(f"    [SISE] open={details['open']}, high={details['high']}, low={details['low']}, vol={details['volume']}")
    except Exception as e:
        print(f"    [WARN] Sise detail fetch failed: {e}")

    return details


def get_stock_data(code, name):
    """Fetch individual stock data from Naver Finance"""
    print(f"[INFO] Fetching stock data for {name} ({code})...")
    url = f'https://finance.naver.com/item/main.naver?code={code}'
    try:
        soup = fetch_page(url)

        # Current price
        today = soup.select_one('.today')
        current = '0'
        if today:
            em = today.select_one('em span.blind')
            if em:
                current = clean_number(em.text)

        # Korean name
        kr_name = name
        for selector in ['.wrap_company h2 a', '.wrap_company h2', '#middle h2']:
            tag = soup.select_one(selector)
            if tag and tag.text.strip():
                kr_name = tag.text.strip()
                break

        # Change info
        no_exday = soup.select_one('.no_exday')
        change = '0'
        change_pct = '0'
        is_up = True

        if no_exday:
            blinds = no_exday.select('span.blind')
            if len(blinds) >= 1:
                change = clean_number(blinds[0].text)
            if len(blinds) >= 2:
                change_pct = clean_pct(blinds[1].text)

            full_text = no_exday.text
            if '\ud558\ub77d' in full_text:
                is_up = False
            em_tags = no_exday.select('em')
            for em in em_tags:
                cls = str(em.get('class', ''))
                if 'ndn' in cls or 'down' in cls:
                    is_up = False
                    break

        # Get detailed data (open/high/low/volume) from sise sub-page
        details = get_stock_sise_details(code)

        # Fallback: try main page aside_invest_info table
        if details['volume'] == '0':
            table = soup.select_one('.aside_invest_info table')
            if table:
                tds = table.select('td span.blind')
                if len(tds) >= 4:
                    details['volume'] = clean_number(tds[3].text)

        print(f"  [OK] {kr_name}: {current}")

        return {
            'code': code,
            'name': kr_name,
            'nameEn': name,
            'current': current,
            'change': change if is_up else f'-{change}',
            'changePct': change_pct if is_up else f'-{change_pct}',
            'direction': 'up' if is_up else 'down',
            'volume': details['volume'],
            'high': details['high'],
            'low': details['low'],
            'open': details['open'],
            'marketCap': details['marketCap'],
        }
    except Exception as e:
        print(f"[ERROR] Failed to fetch stock data for {code}: {e}")
        return None


def get_exchange_rates():
    """Fetch exchange rate data from Naver Finance Market Index"""
    print("[INFO] Fetching exchange rates...")
    url = 'https://finance.naver.com/marketindex/'
    try:
        soup = fetch_page(url)

        rates = []
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

            direction = 'up'
            blind_tags = item.select('.blind')
            for bt in blind_tags:
                txt = bt.text.strip()
                if txt == '\ud558\ub77d':
                    direction = 'down'
                elif txt == '\ubcf4\ud569':
                    direction = 'flat'

            pair = ''
            if 'USD' in name or '\ubbf8\uad6d' in name or '\ub2ec\ub7ec' in name:
                pair = 'USD/KRW'
            elif 'EUR' in name or '\uc720\ub7fd' in name or '\uc720\ub85c' in name:
                pair = 'EUR/KRW'
            elif 'JPY' in name or '\uc77c\ubcf8' in name or '\uc5d4' in name:
                pair = 'JPY/KRW'
            elif 'CNY' in name or '\uc911\uad6d' in name or '\uc704\uc548' in name:
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
    """Fetch oil and gold prices from Naver Finance marketindex page"""
    print("[INFO] Fetching oil prices...")
    oils = []
    found_codes = set()

    # Approach 1: Get from marketindex main page (oilGoldList section)
    try:
        url = 'https://finance.naver.com/marketindex/'
        soup = fetch_page(url)

        oil_items = soup.select('#oilGoldList li')
        if not oil_items:
            # Try alternative selectors
            oil_items = soup.select('.market_data .data_lst li')

        print(f"  [DEBUG] Found {len(oil_items)} items in oilGoldList")

        for item in oil_items:
            name_tag = item.select_one('.h_lst .blind') or item.select_one('.h_lst')
            if not name_tag:
                continue
            name_text = name_tag.text.strip()
            print(f"  [DEBUG] Oil item: {name_text}")

            value_tag = item.select_one('.value')
            value = clean_number(value_tag.text) if value_tag else '0'

            change_tag = item.select_one('.change')
            change = clean_number(change_tag.text) if change_tag else '0'

            direction = 'up'
            for bt in item.select('.blind'):
                txt = bt.text.strip()
                if txt == '\ud558\ub77d':
                    direction = 'down'
                elif txt == '\ubcf4\ud569':
                    direction = 'flat'

            code = ''
            display_name = ''
            unit = ''
            if 'WTI' in name_text or '\uc11c\ubd80\ud14d\uc0ac\uc2a4' in name_text:
                code, display_name, unit = 'OIL_CL', 'WTI', 'USD/barrel'
            elif '\ube0c\ub80c\ud2b8' in name_text or 'Brent' in name_text:
                code, display_name, unit = 'OIL_BRT', 'Brent', 'USD/barrel'
            elif '\ub450\ubc14\uc774' in name_text or 'Dubai' in name_text:
                code, display_name, unit = 'OIL_DU', 'Dubai', 'USD/barrel'
            elif '\uad6d\uc81c\uae08' in name_text or '\uae08' in name_text or 'Gold' in name_text:
                code, display_name, unit = 'GOLD', 'Gold', 'USD/oz'

            if code and value != '0':
                oils.append({
                    'code': code,
                    'name': display_name,
                    'value': value,
                    'change': change,
                    'direction': direction,
                    'unit': unit,
                })
                found_codes.add(code)
                print(f"  [OK] {display_name}: {value}")

    except Exception as e:
        print(f"  [WARN] Marketindex main page failed: {e}")

    # Approach 2: Try individual commodity detail pages for any missing items
    oil_targets = {
        'OIL_CL': {'name': 'WTI', 'unit': 'USD/barrel',
                    'urls': [
                        'https://finance.naver.com/marketindex/commodityDetail.naver?marketindexCd=OIL_CL',
                    ]},
        'OIL_BRT': {'name': 'Brent', 'unit': 'USD/barrel',
                     'urls': [
                         'https://finance.naver.com/marketindex/commodityDetail.naver?marketindexCd=OIL_BRT',
                         'https://finance.naver.com/marketindex/worldDailyQuote.naver?marketindexCd=OIL_BRT&fdtc=2',
                     ]},
        'OIL_DU': {'name': 'Dubai', 'unit': 'USD/barrel',
                    'urls': [
                        'https://finance.naver.com/marketindex/commodityDetail.naver?marketindexCd=OIL_DU',
                        'https://finance.naver.com/marketindex/worldDailyQuote.naver?marketindexCd=OIL_DU&fdtc=2',
                    ]},
    }

    for code, info in oil_targets.items():
        if code in found_codes:
            continue

        value = '0'
        change = '0'
        direction = 'flat'

        for url in info['urls']:
            if value != '0':
                break
            try:
                soup = fetch_page(url)

                # Strategy A: Standard selectors used on most Naver commodity pages
                for sel in ['.no_today .blind', '.no_today em .blind', '.no_today em',
                            '#currentPrice', '.sise_wont', 'p.no_today',
                            '.spot_area .no_today', '.group_spot .current']:
                    tags = soup.select(sel)
                    for tag in tags:
                        v = clean_number(tag.text)
                        if v != '0' and len(v) > 1:
                            value = v
                            break
                    if value != '0':
                        break

                # Strategy B: Look for table-based data (worldDailyQuote pages)
                if value == '0':
                    for tr in soup.select('table tbody tr'):
                        tds = tr.select('td')
                        if len(tds) >= 2:
                            v = clean_number(tds[0].text)
                            if v != '0' and len(v) > 1:
                                try:
                                    float(v)
                                    value = v
                                    c = clean_number(tds[1].text)
                                    if c != '0':
                                        change = c
                                    break
                                except ValueError:
                                    continue

                # Strategy C: Search for price-like patterns near known class names
                if value == '0':
                    for cls in ['spot', 'current', 'price', 'value', 'rate']:
                        for tag in soup.find_all(class_=re.compile(cls, re.I)):
                            v = clean_number(tag.get_text())
                            if v != '0' and len(v) > 1:
                                try:
                                    fv = float(v)
                                    if 10 < fv < 300:
                                        value = v
                                        break
                                except ValueError:
                                    continue
                        if value != '0':
                            break

                # Strategy D: Parse all text for the first number in oil-price range
                if value == '0':
                    body_text = soup.get_text()
                    price_candidates = re.findall(r'\b(\d{2,3}\.\d{1,2})\b', body_text)
                    for pc in price_candidates:
                        try:
                            fv = float(pc)
                            if 10 < fv < 300:
                                value = pc
                                print(f"  [DEBUG] {info['name']} found via regex: {pc}")
                                break
                        except ValueError:
                            continue

                # Get change/direction if we found value but not change
                if value != '0' and change == '0':
                    for sel in ['.no_exday .blind', '.no_exday em .blind',
                                '.change', '.fluctuation']:
                        tags = soup.select(sel)
                        for tag in tags:
                            c = clean_number(tag.text)
                            if c != '0':
                                change = c
                                break
                        if change != '0':
                            break

                if value != '0':
                    direction = 'up'
                    ico = soup.select_one('.no_exday .ico') or soup.select_one('.ico')
                    if ico:
                        ico_cls = str(ico.get('class', ''))
                        ico_txt = ico.text
                        if 'down' in ico_cls or '\ud558\ub77d' in ico_txt:
                            direction = 'down'
                    for blind in soup.select('.blind'):
                        if blind.text.strip() == '\ud558\ub77d':
                            direction = 'down'
                            break

                print(f"  [DEBUG] {info['name']} from {url.split('?')[0].split('/')[-1]}: value={value}")

            except Exception as e:
                print(f"  [WARN] {info['name']} url failed: {e}")

        oils.append({
            'code': code,
            'name': info['name'],
            'value': value,
            'change': change,
            'direction': direction,
            'unit': info['unit'],
        })
        found_codes.add(code)
        print(f"  [OK] {info['name']}: {value}")

    # Gold (if not already found)
    if 'GOLD' not in found_codes:
        try:
            url = 'https://finance.naver.com/marketindex/goldDetail.naver'
            soup = fetch_page(url)

            value = '0'
            for sel in ['.no_today .blind', '.no_today em .blind', '.no_today em']:
                tags = soup.select(sel)
                for tag in tags:
                    v = clean_number(tag.text)
                    if v != '0' and len(v) > 1:
                        value = v
                        break
                if value != '0':
                    break

            change = '0'
            for sel in ['.no_exday .blind', '.no_exday em .blind']:
                tags = soup.select(sel)
                for tag in tags:
                    c = clean_number(tag.text)
                    if c != '0':
                        change = c
                        break
                if change != '0':
                    break

            oils.append({
                'code': 'GOLD',
                'name': 'Gold',
                'value': value,
                'change': change,
                'direction': 'up',
                'unit': 'KRW/g',
            })
            print(f"  [OK] Gold: {value}")
        except Exception as e:
            print(f"  [ERROR] Gold: {e}")

    return oils


def get_news_headlines():
    """Fetch latest financial news headlines with multiple fallback approaches"""
    print("[INFO] Fetching financial news...")

    # Approach 1: Naver Finance main news page
    try:
        url = 'https://finance.naver.com/news/mainnews.naver'
        soup = fetch_page(url)
        headlines = []

        news_items = soup.select('.mainNewsList li')
        if not news_items:
            news_items = soup.select('.newsList li')

        print(f"  [DEBUG] Found {len(news_items)} news items")

        for item in news_items[:10]:
            # Try all a tags in the item (some li have image link + title link)
            a_tags = item.select('a')
            title = ''
            link = ''

            for a_tag in a_tags:
                text = a_tag.get_text(strip=True)
                href = a_tag.get('href', '')

                # Skip image-only links
                if not text and a_tag.select_one('img'):
                    if not link and href:
                        link = href
                    continue

                if text and len(text) > 5:
                    title = text
                    link = href
                    break

            # Fallback: check title attribute
            if not title:
                for a_tag in a_tags:
                    t = a_tag.get('title', '')
                    if t and len(t) > 5:
                        title = t
                        link = a_tag.get('href', '')
                        break

            # Fallback: check dd element
            if not title:
                dd = item.select_one('dd, .articleSubject a, .tit')
                if dd:
                    title = dd.get_text(strip=True)
                    a = dd.select_one('a') if dd.name != 'a' else dd
                    if a:
                        link = a.get('href', '')

            if not link:
                continue
            if link and not link.startswith('http'):
                link = 'https://finance.naver.com' + link

            headlines.append({
                'title': title,
                'link': link,
            })

        # Filter out items with empty titles
        headlines = [h for h in headlines if h['title']]

        if headlines:
            print(f"  [OK] Got {len(headlines)} headlines from mainnews")
            return headlines[:8]
        else:
            print("  [WARN] No headlines extracted from mainnews, trying debug...")
            # Debug: print first item structure
            if news_items:
                print(f"  [DEBUG] First item HTML: {str(news_items[0])[:500]}")

    except Exception as e:
        print(f"  [WARN] Main news approach failed: {e}")

    # Approach 2: Naver Finance news list page (different layout)
    try:
        url = 'https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=258'
        soup = fetch_page(url)
        headlines = []

        items = soup.select('.type06_headline li, .realtimeNewsList li')
        print(f"  [DEBUG] Approach 2: Found {len(items)} items")

        for item in items[:8]:
            a_tags = item.select('a')
            for a_tag in a_tags:
                title = a_tag.get_text(strip=True)
                if title and len(title) > 5:
                    link = a_tag.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://finance.naver.com' + link
                    headlines.append({'title': title, 'link': link})
                    break

        if headlines:
            print(f"  [OK] Got {len(headlines)} headlines from news_list")
            return headlines[:8]

    except Exception as e:
        print(f"  [WARN] News list approach failed: {e}")

    # Approach 3: Naver News economy section
    try:
        url = 'https://news.naver.com/section/101'
        soup = fetch_page(url)
        headlines = []

        # Try multiple selectors for the news section
        for sel in ['.sa_text_strong', '.sa_text_title .sa_text_strong',
                    '.cluster_text_headline', '.list_text a']:
            items = soup.select(sel)
            if items:
                for item in items[:8]:
                    title = item.get_text(strip=True)
                    a_tag = item if item.name == 'a' else item.find_parent('a')
                    link = a_tag.get('href', '') if a_tag else ''
                    if title and len(title) > 5:
                        headlines.append({'title': title, 'link': link})
                break

        if headlines:
            print(f"  [OK] Got {len(headlines)} headlines from news.naver.com")
            return headlines[:8]

    except Exception as e:
        print(f"  [WARN] Naver News approach failed: {e}")

    print("  [WARN] All news approaches failed, returning empty list")
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
