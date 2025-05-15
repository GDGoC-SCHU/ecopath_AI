from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import requests
import json
import google.generativeai as genai
from fastapi.responses import StreamingResponse
from typing import Generator

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY가 설정되지 않았습니다.")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RouteRequest(BaseModel):
    selected_category_from_ui: list[str]
    place_names: list[str]

class LatLng(BaseModel):
    name: str
    lat: float
    lng: float


# 유효한 카테고리 목록 정의
valid_categories = ["숙박", "식당", "카페", "관광지"]

def get_place_location(place_name: str) -> LatLng:
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": place_name,
        "inputtype": "textquery",
        "fields": "geometry,name",
        "key": GOOGLE_API_KEY
    }
    res = requests.get(url, params=params).json()
    if res.get("status") == "OK" and res.get("candidates"):
        loc = res["candidates"][0]["geometry"]["location"]
        return LatLng(name=place_name, lat=loc["lat"], lng=loc["lng"])
    else:
        raise HTTPException(status_code=404, detail=f"장소 '{place_name}'을(를) 찾을 수 없습니다.")

def generate_transportation_guide(categories, names):
    course_lines = [f"{cat}: {name}" for cat, name in zip(categories, names)]
    course_text = " -> ".join(course_lines)
    guide_prompt = f"""
너는 여행 경로 해설 전문가야.

다음 장소들을 주어진 순서대로 여행한다고 할 때,
각 장소 사이를 대중교통(지하철/버스/도보)으로 이동하는 경로를 간단하게 설명해줘.

장소 목록: {course_text}

형식 예:
"A에서 B까지는 지하철 2호선 3정거장, B에서 C까지는 도보 5분"

결과는 한 줄로 간결하게 설명해줘.
"""

    try:
        response = model.generate_content(guide_prompt)
        return response.text.strip()
    except Exception:
        return "이동 경로 설명을 생성하지 못했습니다."

@app.post("/eco_routes_dynamic")
def recommend_ordered_route(data: RouteRequest):
    categories = data.selected_category_from_ui
    names = data.place_names

    if len(categories) != len(names):
        raise HTTPException(status_code=400, detail="카테고리와 장소 수가 일치하지 않습니다.")

    route = []
    for cat, name in zip(categories, names):
        location = get_place_location(name)
        route.append({
            "category": cat,
            "location": location.dict()
        })

    transportation_guide = generate_transportation_guide(categories, names)

    return {
        "recommended_route": route,
        "transportation_guide": transportation_guide
    }


@app.get("/gemini_routes")
def get_gemini_routes(region: str = Query(..., description="추천을 받을 지역명")):
    prompt = f"""
너는 '{region}' 여행 코스를 기획하는 여행 전문가야.

사용자가 '{region}' 여행을 계획하고 있어.

다음 조건에 따라 총 3개의 여행 경로를 추천해줘:
- 각 경로에는 '숙소', '관광지', '식당', '카페'를 각각 1개씩 포함해야 해
- 단, 장소의 순서는 경로마다 반드시 다르게 섞어줘야 해
- 예: 관광지 → 숙소 → 카페 → 식당 또는 카페 → 관광지 → 숙소 → 식당 등
- 동선이 자연스럽고 여행 흐름이 좋은 방식으로 조합해줘
- 각 장소는 실제 존재하는 '{region}' 내 장소여야 하고, 서로 중복되지 않아야 해

그리고 각 경로마다 **대중교통을 이용한 간단한 이동 설명**도 함께 작성해줘.
예: "A에서 B까지는 3호선 지하철, B에서 C까지는 버스 7011번, 도보 5분" 등으로 간단하게.

출력은 반드시 다음 JSON 형식을 따라줘:

{{
  "recommended_routes": [
    {{
      "course": [
        {{ "category": "숙소", "name": "..." }},
        {{ "category": "관광지", "name": "..." }},
        {{ "category": "식당", "name": "..." }},
        {{ "category": "카페", "name": "..." }}
      ],
      "transportation_guide": "..."
    }},
    ...
  ]
}}
"""

    try:
        response = model.generate_content(prompt)
        content = response.text

        start_index = content.find('{')
        end_index = content.rfind('}') + 1
        json_text = content[start_index:end_index]
        parsed = json.loads(json_text)
        return parsed

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini 응답 처리 중 오류 발생: {str(e)}")
    
@app.get("/gemini_routes")
def get_gemini_routes(region: str = Query(..., description="추천을 받을 지역명")):
    prompt = f"""
너는 '{region}' 여행 코스를 기획하는 여행 전문가야.

사용자가 '{region}' 여행을 계획하고 있어.

다음 조건에 따라 총 3개의 여행 경로를 추천해줘:
- 각 경로에는 '숙소', '관광지', '식당', '카페'를 각각 1개씩 포함해야 해
- 단, 장소의 순서는 경로마다 반드시 다르게 섞어줘야 해
- 예: 관광지 → 숙소 → 카페 → 식당 또는 카페 → 관광지 → 숙소 → 식당 등
- 동선이 자연스럽고 여행 흐름이 좋은 방식으로 조합해줘
- 각 장소는 실제 존재하는 '{region}' 내 장소여야 하고, 서로 중복되지 않아야 해

그리고 각 경로마다 **대중교통을 이용한 간단한 이동 설명**도 함께 작성해줘.
예: "A에서 B까지는 3호선 지하철, B에서 C까지는 버스 7011번, 도보 5분" 등으로 간단하게.

출력은 반드시 다음 JSON 형식을 따라줘:

{{
  "recommended_routes": [
    {{
      "course": [
        {{ "category": "숙소", "name": "..." }},
        {{ "category": "관광지", "name": "..." }},
        {{ "category": "식당", "name": "..." }},
        {{ "category": "카페", "name": "..." }}
      ],
      "transportation_guide": "..."
    }},
    ...
  ]
}}
"""

    try:
        response = model.generate_content(prompt)
        content = response.text

        start_index = content.find('{')
        end_index = content.rfind('}') + 1
        json_text = content[start_index:end_index]
        parsed = json.loads(json_text)
        return parsed

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini 응답 처리 중 오류 발생: {str(e)}")
    

def get_gemini_recommend(user_category_answer: str):
    model = genai.GenerativeModel('gemini-2.0-flash')

    system_instruction = (
        """너는 서울의 친환경 여행 전문가야. 
        사용자가 서울에서 특정 카테고리(숙박, 식당, 카페, 관광지)의 지속 가능한 장소를 문의하면, 
        해당 카테고리에 맞는 예시를 3곳 추천해줘. 각 장소에 대해 친환경 요소도 구체적으로 설명해야 해. 
        만약 조건에 맞는 장소를 찾을 수 없다면 죄송하지만, 현재 조건에 맞는 [카테고리명]을(를) 찾을 수 없습니다.라고 답해줘.
       
       출력은 반드시 다음 JSON 형식을 따라줘:

            {{
                "name": "...",
                "description": "...",
                "features": "...",
                ...
            }} 
        """
    )

    user_queries = [
        "서울에 환경을 생각하는 특별한 숙소 없을까?",
        "서울에서 지속 가능한 식재료를 사용하는 음식점 추천해줘.",
        "서울에 친환경적인 카페가 있을까?",
        "서울에서 자연을 느낄 수 있는 지속가능한 관광지 좀 알려줘."
    ]

    category_index = valid_categories.index(user_category_answer)
    user_query = user_queries[category_index]

    messages = [
        {"role": "assistant", "parts": system_instruction},
        {"role": "user", "parts": user_query}
    ]

    response = model.generate_content(messages)
    content = response.text
    start_index = content.find('{')
    end_index = content.rfind('}') + 1
    json_text = content[start_index:end_index]
    parsed = json.loads("[" + json_text + "]")

    # 결과를 반환
    return {"responses": {
        "query": user_query,
        "response": parsed,
    }}

@app.get("/get_gemini_recommend")
def get_gemini_recommend_routes(user_category_answer: str):
    if user_category_answer not in valid_categories:
        raise HTTPException(status_code=400, detail=f"'{user_category_answer}'은(는) 유효한 카테고리가 아닙니다. 유효한 카테고리는 {valid_categories}입니다.")

    
    return get_gemini_recommend(user_category_answer)

