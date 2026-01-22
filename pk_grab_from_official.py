import requests
from bs4 import BeautifulSoup
import time
import json
import os
import re

def get_soup(url, lang="en"):
    # 針對不同語言設定標頭，避免伺服器強制轉址
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9" if lang == "en" else "zh-TW,zh;q=0.9"
    }
    print(f"📡 GET [{lang}]: {url}")
    res = requests.get(url, headers=headers)
    return BeautifulSoup(res.text, 'html.parser')

def get_leagues_from_article(url, lang="en"):
    soup = get_soup(url, lang)
    items = soup.find_all('div', attrs={"data-slot": "GblScheduleBlockItem"})
    schedule_data = []
    
    for item in items:
        start_ts = int(item.get('data-start-timestamp', 0))
        end_ts = int(item.get('data-end-timestamp', 0))
        
        # 抓取聯盟名稱
        league_divs = item.find_all('div', class_=lambda x: x and 'League' in x)
        names = [d.get_text(strip=True).replace('*', '') for d in league_divs if d.get_text(strip=True)]
        
        schedule_data.append({
            "start": start_ts, 
            "end": end_ts, 
            "leagues": names
        })
    return schedule_data

def map_to_pvpoke_id_and_cp(en_name):
    name = en_name.lower()
    cp = 1500
    
    # 1. 判斷 CP
    if "master" in name: cp = 10000
    elif "ultra" in name: cp = 2500
    elif "little" in name: cp = 500
    
    # 2. 判斷 PvPoke ID
    # 核心聯盟處理
    if "great league" in name and "remix" not in name: return "all", 1500
    if "ultra league" in name and "premier" not in name: return "all", 2500
    if "master league" in name and "premier" not in name: return "all", 10000
    
    # 特殊盃賽處理
    # 邏輯：移除 "Cup", "League", "Edition", "Version" 等雜訊
    clean_name = name.replace(" cup", "").replace(" league", "").replace(" edition", "").replace(" version", "")
    
    # 取最後一個單字作為 ID (通常是 Cup 的名字，如 "Retro" -> "retro")
    # 但遇到像 "Ultra Premier" 這種雙字的，要小心處理
    if "premier" in clean_name:
        pvp_id = "premier" 
        if "classic" in clean_name: pvp_id = "premierclassic"
    else:
        pvp_id = clean_name.strip().split(" ")[-1]
    
    # 3. 強制對應表 (手動修正一些 PvPoke 命名不規則的)
    manual_map = {
        "catch": "catch",
        "willpower": "willpower",
        "evolution": "evolution",
        "fantasy": "fantasy",
        "fighting": "fighting",
        "flying": "flying",
        "fossil": "fossil",
        "holiday": "holiday",
        "halloween": "halloween",
        "jungle": "jungle",
        "love": "love",
        "mountain": "mountain",
        "spring": "spring",
        "summer": "summer",
        "sunshine": "sunshine",
        "retro": "retro",
        "remix": "remix"
    }
    
    # 如果算出來的 ID 在對應表裡，就用對應表的 (保險)
    if pvp_id in manual_map:
        pvp_id = manual_map[pvp_id]

    return pvp_id, cp

def run_automation():
    base_url = "https://pokemongolive.com"
    news_list_url = f"{base_url}/zh_hant/news"
    
    # 第一次請求只為了找文章連結
    soup = get_soup(news_list_url, "zh")
    
    zh_article_url = None
    for a in soup.find_all('a', href=True):
        if "對戰聯盟" in a.get_text() and "賽季更新" in a.get_text():
            href = a['href']
            zh_article_url = base_url + href if not href.startswith('http') else href
            break
    
    if not zh_article_url:
        print("❌ 找不到最新的對戰聯盟文章")
        return

    # ★★★ 關鍵修正：使用 Regex 無視大小寫取代 ★★★
    en_article_url = re.sub(r'/zh[-_]hant/', '/en/', zh_article_url, flags=re.IGNORECASE)
    
    print(f"🔗 鎖定中文文章: {zh_article_url}")
    print(f"🔗 鎖定英文文章: {en_article_url}")

    zh_data = get_leagues_from_article(zh_article_url, "zh")
    en_data = get_leagues_from_article(en_article_url, "en")
    
    current_ms = int(time.time() * 1000)
    
    manifest = {
        "last_updated_human": time.ctime(),
        "active_leagues": []
    }
    
    # 比對邏輯
    for i in range(len(zh_data)):
        # 確保索引不超出範圍 (以防萬一中英文版區塊數量不一致)
        if i >= len(en_data): break
        
        if zh_data[i]['start'] <= current_ms <= zh_data[i]['end']:
            for zh, en in zip(zh_data[i]['leagues'], en_data[i]['leagues']):
                pvp_id, cp = map_to_pvpoke_id_and_cp(en)
                
                print(f"✅ 發現: {zh} ({en}) -> ID: {pvp_id}, CP: {cp}")
                
                manifest["active_leagues"].append({
                    "name_zh": zh,
                    "name_en": en,
                    "pvpoke_id": pvp_id,
                    "cp": cp,
                    # 預先組好 JSON URL 方便 Worker 使用
                    "file_name": f"rankings_{cp}.json" if pvp_id == "all" else f"rankings_{pvp_id}_{cp}.json"
                })

    os.makedirs('data', exist_ok=True)
    with open('data/manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"🎉 完成! 產出 {len(manifest['active_leagues'])} 筆資料。")

if __name__ == "__main__":
    run_automation()
