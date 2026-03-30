import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime

API_KEY = st.text_input("🔑 YouTube API Key 입력", type="password")

def parse_duration(duration):
    pattern = re.compile(r'PT(\d+H)?(\d+M)?(\d+S)?')
    match = pattern.match(duration)
    h = int(match.group(1)[:-1]) if match.group(1) else 0
    m = int(match.group(2)[:-1]) if match.group(2) else 0
    s = int(match.group(3)[:-1]) if match.group(3) else 0
    return h*3600 + m*60 + s

def classify(duration, title):
    if duration <= 180 or "#shorts" in title.lower():
        return "SHORTS"
    return "LONG"

def search_youtube(query, max_results):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": max_results,
        "type": "video",
        "key": API_KEY
    }
    return requests.get(url, params=params).json()

def get_video_details(ids):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,contentDetails,statistics",
        "id": ",".join(ids),
        "key": API_KEY
    }
    return requests.get(url, params=params).json()

def get_channel_details(ids):
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "part": "statistics",
        "id": ",".join(ids),
        "key": API_KEY
    }
    return requests.get(url, params=params).json()

st.title("📊 YouTube 분석기")

query = st.text_input("검색 키워드")
count = st.slider("영상 개수", 10, 50, 20)

if st.button("🔍 분석 시작"):
    if not API_KEY:
        st.warning("API 키를 입력하세요!")
    else:
        data = search_youtube(query, count)
        items = data.get("items", [])

        video_ids = [i["id"]["videoId"] for i in items]
        channel_ids = [i["snippet"]["channelId"] for i in items]

        video_data = get_video_details(video_ids)
        channel_data = get_channel_details(channel_ids)

        channel_map = {
            c["id"]: int(c["statistics"].get("subscriberCount", 0))
            for c in channel_data.get("items", [])
        }

        rows = []

        for v in video_data.get("items", []):
            vid = v["id"]
            title = v["snippet"]["title"]
            channel = v["snippet"]["channelTitle"]
            channel_id = v["snippet"]["channelId"]
            views = int(v["statistics"].get("viewCount", 0))
            subs = channel_map.get(channel_id, 0)
            duration = parse_duration(v["contentDetails"]["duration"])

            ratio = views / subs if subs > 0 else 0
            vtype = classify(duration, title)

            rows.append({
                "제목": title,
                "채널": channel,
                "조회수": views,
                "구독자": subs,
                "조회수/구독자": round(ratio, 4),
                "길이(초)": duration,
                "유형": vtype,
                "링크": f"https://youtube.com/watch?v={vid}"
            })

        df = pd.DataFrame(rows)
        df = df.sort_values("조회수/구독자", ascending=False)

        st.dataframe(df)

        # 엑셀 다운로드
        file_name = f"youtube_{query}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        df.to_excel(file_name, index=False)

        with open(file_name, "rb") as f:
            st.download_button("📥 엑셀 다운로드", f, file_name)
