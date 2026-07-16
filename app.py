import os
import asyncio
import urllib.request
from flask import Flask, render_template, request, jsonify, Response
from xhamster_api.api import Client

app = Flask(__name__)

async def fetch_video_data(query):
    client = Client()
    results = []
    
    # ১. যদি সরাসরি লিংক হয় (যেমন: https://xhamster.com/videos/...)
    if "xhamster.com/videos/" in query or "xhamster.com/shorts/" in query:
        try:
            if "/shorts/" in query:
                video = await client.get_short(query)
            else:
                video = await client.get_video(query)
                
            results.append({
                "title": video.title,
                "thumbnail": getattr(video, 'thumbnail', getattr(video, 'thumb_url', '')),
                "m3u8": video.m3u8_base_url,
                "url": query
            })
        except Exception as e:
            print(f"Error: {e}")
            
    # ২. যদি কোনো নাম লিখে সার্চ হয়
    else:
        try:
            async for scrape_result in client.search_videos(query=query, pages=1):
                video = scrape_result.video
                v_url = f"https://xhamster.com/videos/{video.video_id}"
                results.append({
                    "title": video.title,
                    "thumbnail": video.thumbnail,
                    "m3u8": video.m3u8_base_url,
                    "url": v_url
                })
        except Exception as e:
            print(f"Error: {e}")

    return results

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q')
    if not query:
        return jsonify([])
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    data = loop.run_until_complete(fetch_video_data(query))
    return jsonify(data)

# ডাউনলোডের ম্যাজিক রুট!
@app.route('/download_file')
def download_file():
    m3u8_url = request.args.get('url')
    title = request.args.get('title', 'video').replace(" ", "_")
    
    if not m3u8_url:
        return "No URL provided", 400
        
    try:
        req = urllib.request.Request(m3u8_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            m3u8_content = response.read()
            
        # এটি ব্রাউজারকে ফাইলটি ডাউনলোড করতে বাধ্য করবে
        return Response(
            m3u8_content,
            mimetype="application/vnd.apple.mpegurl",
            headers={"Content-disposition": f"attachment; filename={title}.m3u8"}
        )
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run()
