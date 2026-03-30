import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime, timezone

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
only_algo = st.checkbox("알고리즘 탄 영상만 보기")

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

            # 업로드 날짜 계산
            published_at = v["snippet"]["publishedAt"]
            published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            days = max((now - published_dt).days, 1)

            # 기본 지표
            ratio = views / subs if subs > 0 else 0
            diff = views - subs
            views_per_day = views / days
            vtype = classify(duration, title)

            # 🔥 알고리즘 추정 + 이유
            algo_flag = "NO"
            reason = "일반 노출"

            if ratio >= 5 and days <= 7:
                algo_flag = "YES"
                reason = "🔥 강한 추천 (초기 + 높은 조회수/구독자 비율)"
            elif ratio >= 3:
                algo_flag = "YES"
                reason = "추천 가능성 높음 (조회수/구독자 높음)"
            elif views_per_day >= 10000:
                algo_flag = "YES"
                reason = "빠른 조회수 증가"
            elif vtype == "SHORTS" and ratio >= 2:
                algo_flag = "YES"
                reason = "Shorts 알고리즘 반응"

            rows.append({
                "제목": title,
                "채널": channel,
                "조회수": views,
                "구독자": subs,
                "조회수/구독자": round(ratio, 4),
                "조회수-구독자": diff,
                "일평균조회수": int(views_per_day),
                "업로드일수": days,
                "유형": vtype,
                "알고리즘탐지": algo_flag,
                "이유": reason,
                "링크": f"https://youtube.com/watch?v={vid}"
            })

        df = pd.DataFrame(rows)
        if only_algo:
            df = df[df["알고리즘탐지"] == "YES"]
        df = df.sort_values(
            by=["알고리즘탐지", "조회수/구독자"],
            ascending=[False, False]
        )
        df = df.sort_values(sort_option, ascending=False)

        st.dataframe(df)

        # 엑셀 다운로드
        file_name = f"youtube_{query}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        df.to_excel(file_name, index=False)

        with open(file_name, "rb") as f:
            st.download_button("📥 엑셀 다운로드", f, file_name)
