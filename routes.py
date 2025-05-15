from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import random
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("환경 변수 GOOGLE_API_KEY가 설정되지 않았습니다.")

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

@app.post("/eco_routes_dynamic")
def recommend_multiple_routes(data: RouteRequest):
    categories = data.selected_category_from_ui
    names = data.place_names

    if len(categories) != len(names):
        raise HTTPException(status_code=400, detail="카테고리와 장소 수가 일치하지 않습니다.")


    place_dict = {}
    for cat, name in zip(categories, names):
        place_dict[cat] = get_place_location(name)

    if "숙소" not in place_dict:
        raise HTTPException(status_code=400, detail="숙소는 반드시 포함되어야 합니다.")

    fixed_start = "숙소"
    movable_categories = [cat for cat in place_dict.keys() if cat != fixed_start]

    if len(movable_categories) < 2:
        raise HTTPException(status_code=400, detail="숙소 외에 최소 2개의 장소가 필요합니다.")

    route_combinations = []
    used_orders = set()

    for _ in range(10):  
        random_order = tuple(random.sample(movable_categories, len(movable_categories)))
        if random_order not in used_orders:
            used_orders.add(random_order)
            final_order = [fixed_start] + list(random_order)
            route_combinations.append(final_order)
        if len(route_combinations) >= 2:
            break

    result = []
    for route in route_combinations:
        ordered_places = [place_dict[cat] for cat in route]
        result.append({
            "order": route,
            "locations": [place.dict() for place in ordered_places]
        })

    return {
        "recommended_routes": result
    }