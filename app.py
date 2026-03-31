import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime, timezone
from io import BytesIO

st.set_page_config(page_title="YouTube 분석기", page_icon="📊", layout="wide")

API_KEY = st.text_input("🔑 YouTube API Key 입력", type="password")


def parse_duration(duration):
    pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
    match = pattern.match(duration)
    if not match:
        return 0

    h = int(match.group(1)) if match.group(1) else 0
    m = int(match.group(2)) if match.group(2) else 0
    s = int(match.group(3)) if match.group(3) else 0
    return h * 3600 + m * 60 + s


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
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_video_details(ids):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,contentDetails,statistics",
        "id": ",".join(ids),
        "key": API_KEY
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_channel_details(ids):
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "part": "statistics",
        "id": ",".join(ids),
        "key": API_KEY
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def make_excel_file(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="results")
    output.seek(0)
    return output


st.title("📊 YouTube 분석기")

query = st.text_input("검색 키워드")
count = st.slider("영상 개수", 10, 50, 20)

sort_option = st.selectbox(
    "정렬 기준 선택",
    ["조회수/구독자", "조회수-구독자", "조회수", "구독자", "일평균조회수", "업로드일수"]
)

only_algo = st.checkbox("알고리즘 탄 영상만 보기")

if st.button("🔍 분석 시작"):
    if not API_KEY:
        st.warning("API 키를 입력하세요!")
    elif not query.strip():
        st.warning("검색 키워드를 입력하세요!")
    else:
        try:
            data = search_youtube(query, count)
            items = data.get("items", [])

            if not items:
                st.warning("검색 결과가 없습니다.")
            else:
                video_ids = [i["id"]["videoId"] for i in items if "videoId" in i["id"]]
                channel_ids = [i["snippet"]["channelId"] for i in items]

                if not video_ids:
                    st.warning("영상 ID를 가져오지 못했습니다.")
                else:
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

                        published_at = v["snippet"]["publishedAt"]
                        published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        days = max((now - published_dt).days, 1)

                        ratio = views / subs if subs > 0 else 0
                        diff = views - subs
                        views_per_day = views / days
                        vtype = classify(duration, title)

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
                            "길이(초)": duration,
                            "유형": vtype,
                            "알고리즘탐지": algo_flag,
                            "이유": reason,
                            "링크": f"https://youtube.com/watch?v={vid}"
                        })

                    df = pd.DataFrame(rows)

                    if df.empty:
                        st.warning("분석할 데이터가 없습니다.")
                    else:
                        if only_algo:
                            df = df[df["알고리즘탐지"] == "YES"]

                        if df.empty:
                            st.warning("조건에 맞는 영상이 없습니다.")
                        else:
                            df = df.sort_values(
                                by=[sort_option, "조회수/구독자"],
                                ascending=[False, False]
                            ).reset_index(drop=True)

                            st.dataframe(df, use_container_width=True)

                            excel_data = make_excel_file(df)
                            file_name = f"youtube_{query}_{datetime.now().strftime('%Y%m%d')}.xlsx"

                            st.download_button(
                                "📥 엑셀 다운로드",
                                data=excel_data,
                                file_name=file_name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )

        except requests.HTTPError as e:
            st.error(f"API 요청 오류: {e}")
        except requests.RequestException as e:
            st.error(f"네트워크 오류: {e}")
        except Exception as e:
            st.error(f"오류 발생: {e}")
