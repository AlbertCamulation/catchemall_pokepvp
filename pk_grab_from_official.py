import requests
from bs4 import BeautifulSoup
import time
import json
import os

def get_soup(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    res = requests.get(url, headers=headers)
    return BeautifulSoup(res.text, 'html.parser')

def get_leagues_from_article(url):
    soup = get_soup(url)
    items = soup.find_all('div', attrs={"data-slot": "GblScheduleBlockItem"})
    schedule_data = []
    for item in items:
        start_ts = int(item.get('data-start-timestamp', 0))
        end_ts = int(item.get('data-end-timestamp', 0))
        league_divs = item.find_all('div', class_=lambda x: x and 'League' in x)
        names = [d.get_text(strip=True).replace('*', '') for d in league_divs if d.get_text(strip=True)]
        schedule_data.append({"start": start_ts, "end": end_ts, "leagues": names})
    return schedule_data

def map_to_pvpoke_id_and_cp(en_name):
    name = en_name.lower()
    cp = 1500
    if "ultra" in name: cp = 2500
    if "master" in name: cp = 10000
    
    if "great league" in name and "premier" not in name: return "all", 1500
    if "ultra league" in name and "premier" not in name: return "all", 2500
    if "master league" in name and "premier" not in name: return "all", 10000
    
    # 簡單邏輯：取空格最後一個字，例如 "Retro Cup" -> "retro"
    pvp_id = name.replace(" cup", "").replace(" league", "").strip().split(" ")[-1]
    return pvp_id, cp

def run_automation():
    # 偵測最新文章連結 (動態抓取第一篇包含對戰聯盟關鍵字的連結)
    base_url = "https://pokemongolive.com"
    news_list_url = f"{base_url}/zh_hant/news"
    soup = get_soup(news_list_url)
    
    zh_article_url = None
    for a in soup.find_all('a', href=True):
        if "對戰聯盟" in a.get_text() and "賽季更新" in a.get_text():
            zh_article_url = base_url + a['href'] if not a['href'].startswith('http') else a['href']
            break
    
    if not zh_article_url:
        print("❌ 找不到最新的對戰聯盟文章")
        return

    en_article_url = zh_article_url.replace("/zh_hant/", "/en/")
    
    print(f"🔗 正在掃描中文: {zh_article_url}")
    print(f"🔗 正在掃描英文: {en_article_url}")

    zh_data = get_leagues_from_article(zh_article_url)
    en_data = get_leagues_from_article(en_article_url)
    current_ms = int(time.time() * 1000)
    
    manifest = {
        "last_updated_human": time.ctime(),
        "active_leagues": []
    }
    
    for i in range(len(zh_data)):
        if zh_data[i]['start'] <= current_ms <= zh_data[i]['end']:
            for zh, en in zip(zh_data[i]['leagues'], en_data[i]['leagues']):
                pvp_id, cp = map_to_pvpoke_id_and_cp(en)
                manifest["active_leagues"].append({
                    "name_zh": zh,
                    "name_en": en,
                    "pvpoke_id": pvp_id,
                    "cp": cp
                })

    # 自動建立 data 資料夾
    os.makedirs('data', exist_ok=True)
    with open('data/manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 成功! 產出 {len(manifest['active_leagues'])} 個聯盟資料到 data/manifest.json")

if __name__ == "__main__":
    run_automation()
