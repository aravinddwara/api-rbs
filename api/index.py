from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import httpx
import asyncio
from typing import Optional
import time
from datetime import datetime

# Initialize FastAPI app
app = FastAPI(
    title="NetMirror Stream API",
    description="API to extract streaming URLs from Netflix Mirror services",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_URL = "https://net20.cc"
NEW_URL = "https://net51.cc"
COOKIE_CACHE = {}
COOKIE_EXPIRY = 15 * 60 * 60

# Provider configurations
PROVIDERS = {
    "netflix": {
        "name": "Netflix",
        "ott": "nf",
        "poster_base": "https://imgcdn.kim/poster/v",
        "poster_bg": "https://imgcdn.kim/poster/h",
        "episode_poster": "https://imgcdn.kim/epimg/150",
        "search_endpoint": "/search.php",
        "post_endpoint": "/post.php",
        "episodes_endpoint": "/episodes.php",
        "playlist_endpoint": "/tv/playlist.php",
        "user_token": "233123f803cf02184bf6c67e149cdd50"
    },
    "primevideo": {
        "name": "PrimeVideo",
        "ott": "pv",
        "poster_base": "https://wsrv.nl/?url=https://imgcdn.kim/pv/v",
        "poster_bg": "https://wsrv.nl/?url=https://imgcdn.kim/pv/h",
        "episode_poster": "https://imgcdn.kim/pvepimg/150",
        "search_endpoint": "/pv/search.php",
        "post_endpoint": "/pv/post.php",
        "episodes_endpoint": "/pv/episodes.php",
        "playlist_endpoint": "/pv/playlist.php"
    },
    "hotstar": {
        "name": "Hotstar",
        "ott": "hs",
        "poster_base": "https://imgcdn.kim/hs/v",
        "poster_bg": "https://imgcdn.kim/hs/h",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "search_endpoint": "/mobile/hs/search.php",
        "post_endpoint": "/mobile/hs/post.php",
        "episodes_endpoint": "/mobile/hs/episodes.php",
        "playlist_endpoint": "/mobile/hs/playlist.php"
    },
    "disneyplus": {
        "name": "Disney Plus",
        "ott": "dp",
        "poster_base": "https://imgcdn.kim/hs/v",
        "poster_bg": "https://imgcdn.kim/hs/h",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "search_endpoint": "/mobile/hs/search.php",
        "post_endpoint": "/mobile/hs/post.php",
        "episodes_endpoint": "/mobile/hs/episodes.php",
        "playlist_endpoint": "/mobile/hs/playlist.php"
    }
}


async def get_bypass_cookie() -> str:
    """Get bypass cookie with caching"""
    current_time = time.time()
    
    if "cookie" in COOKIE_CACHE and "timestamp" in COOKIE_CACHE:
        if current_time - COOKIE_CACHE["timestamp"] < COOKIE_EXPIRY:
            return COOKIE_CACHE["cookie"]
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for attempt in range(5):
            try:
                response = await client.post(f"{BASE_URL}/tv/p.php")
                data = response.json()
                
                if data.get("r") == "n":
                    cookie = response.cookies.get("t_hash_t", "")
                    if cookie:
                        COOKIE_CACHE["cookie"] = cookie
                        COOKIE_CACHE["timestamp"] = current_time
                        return cookie
                
                await asyncio.sleep(1)
            except Exception:
                if attempt == 4:
                    raise
                await asyncio.sleep(2)
    
    raise HTTPException(status_code=500, detail="Failed to obtain bypass cookie")


def get_unix_time() -> int:
    return int(time.time() * 1000)


def convert_runtime(runtime: str) -> Optional[int]:
    if not runtime:
        return None
    total = 0
    for part in runtime.split():
        if part.endswith('h'):
            total += int(part[:-1]) * 60
        elif part.endswith('m'):
            total += int(part[:-1])
    return total if total > 0 else None


@app.get("/")
async def root():
    return {
        "name": "NetMirror Stream API",
        "version": "1.0.0",
        "providers": list(PROVIDERS.keys()),
        "status": "online"
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/{provider}/search")
async def search(provider: str, query: str = Query(...)):
    if provider not in PROVIDERS:
        raise HTTPException(400, f"Invalid provider: {provider}")
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {"t_hash_t": cookie, "hd": "on", "ott": config["ott"]}
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE_URL}/home"}
    url = f"{BASE_URL}{config['search_endpoint']}?s={query}&t={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        data = response.json()
        
        results = []
        for item in data.get("searchResult", []):
            poster = f"{config['poster_base']}/{item['id']}.jpg"
            if provider == "primevideo":
                poster += "&w=500"
            
            results.append({
                "id": item["id"],
                "title": item["t"],
                "provider": provider,
                "poster_url": poster
            })
        
        return {"provider": provider, "query": query, "results": results, "count": len(results)}


@app.get("/api/{provider}/details")
async def get_details(provider: str, id: str = Query(...)):
    if provider not in PROVIDERS:
        raise HTTPException(400, f"Invalid provider: {provider}")
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {"t_hash_t": cookie, "hd": "on", "ott": config["ott"]}
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE_URL}/home"}
    url = f"{BASE_URL}{config['post_endpoint']}?id={id}&t={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        data = response.json()
        
        episodes = []
        if data.get("episodes") and data["episodes"][0]:
            for ep in data["episodes"]:
                if ep:
                    episodes.append({
                        "id": ep["id"],
                        "title": ep["t"],
                        "episode": int(ep["ep"].replace("E", "")) if ep.get("ep") else None,
                        "season": int(ep["s"].replace("S", "")) if ep.get("s") else None,
                        "runtime": ep.get("time", "").replace("m", ""),
                        "poster_url": f"{config['episode_poster']}/{ep['id']}.jpg"
                    })
        
        cast = [n.strip() for n in data.get("cast", "").split(",")] if data.get("cast") else []
        genres = [g.strip() for g in data.get("genre", "").split(",") if g.strip()]
        rating = data.get("match", "").replace("IMDb ", "") if data.get("match") else None
        
        poster = f"{config['poster_base']}/{id}.jpg"
        bg = f"{config['poster_bg']}/{id}.jpg"
        if provider == "primevideo":
            poster += "&w=500"
            bg += "&w=500"
        
        return {
            "id": id,
            "title": data["title"],
            "description": data.get("desc"),
            "year": data.get("year"),
            "type": "movie" if not episodes else "series",
            "poster_url": poster,
            "background_url": bg,
            "genres": genres,
            "cast": cast,
            "rating": rating,
            "runtime_minutes": convert_runtime(data.get("runtime", "")),
            "content_rating": data.get("ua"),
            "provider": provider,
            "episodes": episodes,
            "total_episodes": len(episodes)
        }


@app.get("/api/{provider}/stream")
async def get_stream_urls(provider: str, id: str = Query(...), title: str = Query("")):
    if provider not in PROVIDERS:
        raise HTTPException(400, f"Invalid provider: {provider}")
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {"t_hash_t": cookie, "hd": "on", "ott": config["ott"]}
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE_URL}/home"}
    url = f"{NEW_URL}{config['playlist_endpoint']}?id={id}&t={title}&tm={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        playlist = response.json()
        
        streams = []
        subtitles = []
        
        for item in playlist:
            for source in item.get("sources", []):
                file_url = source["file"]
                if provider in ["netflix", "primevideo"]:
                    file_url = file_url.replace("/tv/", "/")
                
                stream_url = f"{NEW_URL}/{file_url}" if not file_url.startswith("http") else file_url
                quality = file_url.split("q=")[1].split("&")[0] if "q=" in file_url else "HD"
                
                streams.append({
                    "url": stream_url,
                    "quality": source.get("label", quality),
                    "type": source.get("type", "m3u8"),
                    "headers": {"Referer": f"{NEW_URL}/home", "Cookie": "hd=on"}
                })
            
            for track in item.get("tracks", []):
                if track.get("kind") == "captions":
                    sub_url = track.get("file", "")
                    if sub_url and not sub_url.startswith("http"):
                        sub_url = f"https:{sub_url}" if sub_url.startswith("//") else sub_url
                    
                    subtitles.append({
                        "language": track.get("label", "Unknown"),
                        "url": sub_url
                    })
        
        return {
            "id": id,
            "title": title,
            "provider": provider,
            "streams": streams,
            "subtitles": subtitles,
            "timestamp": datetime.now().isoformat()
        }


# Vercel handler
handler = Mangum(app, lifespan="off")
