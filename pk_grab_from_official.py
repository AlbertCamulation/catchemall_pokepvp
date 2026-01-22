import requests
from bs4 import BeautifulSoup
import time
import json
import os
import re

# ==========================================
# 1. 基礎設定
# ==========================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_soup(url, lang="en"):
    headers = HEADERS.copy()
    headers["Accept-Language"] = "en-US,en;q=0.9" if lang == "en" else "zh-TW,zh;q=0.9"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        return BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"❌ 請求失敗: {e}")
        return None

# ==========================================
# 2. 核心：智慧型連結檢查 (Smart Probe)
# ==========================================
def find_valid_pvpoke_url(pvpoke_id, cp):
    """
    暴力測試：找出該聯盟真正存在的 JSON 檔案網址
    """
    base_repo = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings"
    
    # 預測可能的路徑組合
    # 組合 A: 標準路徑 (例如: rankings/retro/overall/rankings_1500.json)
    # 組合 B: 帶 ID 的檔名 (例如: rankings/premier/overall/rankings_premier_2500.json)
    
    candidates = []
    
    # 針對 "Ultra Premier" 這種特殊情況，它可能在 premier 資料夾，也可能在 ultra_premier
    ids_to_try = [pvpoke_id]
    if pvpoke_id == "ultra_premier": ids_to_try.append("premier")
    if pvpoke_id == "premier": ids_to_try.append("ultra_premier")

    for pid in ids_to_try:
        # 檔名格式 1: rankings_{cp}.json
        candidates.append(f"{base_repo}/{pid}/overall/rankings_{cp}.json")
        # 檔名格式 2: rankings_{id}_{cp}.json
        candidates.append(f"{base_repo}/{pid}/overall/rankings_{pid}_{cp}.json")

    print(f"🔎 正在偵測 {pvpoke_id} (CP {cp})...")

    for url in candidates:
        try:
            # 使用 HEAD 請求 (只抓檔頭，不抓內容，速度極快且省流量)
            res = requests.head(url, headers=HEADERS, timeout=3)
            if res.status_code == 200:
                print(f"   ✅ 找到有效檔案: {url}")
                return url
        except:
            pass
    
    print(f"   ❌ 找不到任何有效檔案 (可能 PvPoke 尚未更新)")
    return None

# ==========================================
# 3. 爬蟲邏輯 (解析官網)
# ==========================================
def get_leagues_from_article(url, lang="en"):
    soup = get_soup(url, lang)
    if not soup: return []
    
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
    
    if "master" in name: cp = 10000
    elif "ultra" in name: cp = 2500
    elif "little" in name: cp = 500
    
    clean_name = name.replace(" cup", "").replace(" league", "").replace(" edition", "").replace(" version", "")
    
    if "great league" in name and "remix" not in name: return "all", 1500
    if "ultra league" in name and "premier" not in name: return "all", 2500
    if "master league" in name and "premier" not in name: return "all", 10000
    
    # 特殊處理: Ultra Premier
    if "premier" in clean_name:
        if "ultra" in name: return "premier", 2500 # 通常 Ultra Premier 放在 premier 資料夾
        if "master" in name: return "premier", 10000
        return "premier", cp

    pvp_id = clean_name.strip().split(" ")[-1]
    
    manual_map = {
        "catch": "catch", "holiday": "holiday", "remix": "remix", 
        "retro": "retro", "fantasy": "fantasy", "willpower": "willpower", 
        "sunshine": "sunshine", "halloween": "halloween", "evolution": "evolution"
    }
    
    if pvp_id in manual_map: pvp_id = manual_map[pvp_id]
    return pvp_id, cp

# ==========================================
# 4. 主程式執行
# ==========================================
def run_automation():
    base_url = "https://pokemongolive.com"
    news_list_url = f"{base_url}/zh_hant/news"
    
    soup = get_soup(news_list_url, "zh")
    if not soup: return

    zh_article_url = None
    for a in soup.find_all('a', href=True):
        if "對戰聯盟" in a.get_text() and "賽季更新" in a.get_text():
            href = a['href']
            zh_article_url = base_url + href if not href.startswith('http') else href
            break
    
    if not zh_article_url:
        print("❌ 找不到最新的對戰聯盟文章")
        return

    en_article_url = re.sub(r'/zh[-_]hant/', '/en/', zh_article_url, flags=re.IGNORECASE)
    
    print(f"🔗 中文: {zh_article_url}")
    print(f"🔗 英文: {en_article_url}")

    zh_data = get_leagues_from_article(zh_article_url, "zh")
    en_data = get_leagues_from_article(en_article_url, "en")
    
    current_ms = int(time.time() * 1000)
    
    manifest = {
        "last_updated_human": time.ctime(),
        "active_leagues": []
    }
    
    for i in range(len(zh_data)):
        if i >= len(en_data): break
        
        if zh_data[i]['start'] <= current_ms <= zh_data[i]['end']:
            for zh, en in zip(zh_data[i]['leagues'], en_data[i]['leagues']):
                pvp_id, cp = map_to_pvpoke_id_and_cp(en)
                
                # ★★★ 關鍵：在這裡進行網址偵測 ★★★
                valid_url = find_valid_pvpoke_url(pvp_id, cp)
                
                if valid_url:
                    manifest["active_leagues"].append({
                        "name_zh": zh,
                        "name_en": en,
                        "pvpoke_id": pvp_id,
                        "cp": cp,
                        "json_url": valid_url # 直接把測試成功的網址存進去
                    })
                else:
                    print(f"⚠️ 跳過 {zh}: PvPoke 上找不到對應檔案")

    os.makedirs('data', exist_ok=True)
    with open('data/manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"🎉 成功產出 {len(manifest['active_leagues'])} 筆有效資料！")

if __name__ == "__main__":
    run_automation()
