import os
import asyncio
from flask import Flask, render_template, request, jsonify, send_file
from xhamster_api import Client

app = Flask(__name__)

# ভিডিও সেভ করার জন্য একটি ফোল্ডার
DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

async def search_videos_async(query):
    client = Client()
    results = []
    async for scrape_result in client.search_videos(query=query, pages=1):
        video = scrape_result.video
        results.append({
            "title": video.title,
            "thumbnail": video.thumbnail,
            "m3u8": video.m3u8_base_url
        })
    return results

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    data = loop.run_until_complete(search_videos_async(query))
    return jsonify(data)

# ডাউনলোডের জন্য নতুন রুট
@app.route('/download_video')
def download_video():
    m3u8_url = request.args.get('url')
    title = request.args.get('title', 'video').replace(" ", "_")
    # যেহেতু ফ্রি সার্ভারে ভিডিও কনভার্ট করা কঠিন, তাই আমরা সরাসরি m3u8 লিঙ্কটি দিয়ে দিচ্ছি 
    # অথবা ব্যবহারকারীকে লিঙ্কটি কপি করার সুযোগ দিচ্ছি।
    return jsonify({"download_url": m3u8_url})

if __name__ == '__main__':
    app.run()
