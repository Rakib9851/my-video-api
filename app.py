import os
import asyncio
from flask import Flask, render_template, request, jsonify
from xhamster_api import Client

app = Flask(__name__)

async def get_data_async(query):
    client = Client()
    results = []
    
    # যদি ইনপুটটি সরাসরি একটি লিঙ্ক হয়
    if "xhamster.com" in query:
        try:
            video = await client.get_video(query)
            results.append({
                "title": video.title,
                "thumbnail": video.thumbnail,
                "m3u8": video.m3u8_base_url,
                "uploader": video.uploader_name
            })
        except:
            pass
    # যদি ইনপুটটি কোনো নাম হয় তবে সার্চ করবে
    else:
        async for scrape_result in client.search_videos(query=query, pages=1):
            video = scrape_result.video
            results.append({
                "title": video.title,
                "thumbnail": video.thumbnail,
                "m3u8": video.m3u8_base_url,
                "uploader": video.uploader_name
            })
    return results

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q')
    if not query: return jsonify([])
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        data = loop.run_until_complete(get_data_async(query))
        return jsonify(data)
    finally:
        loop.close()

if __name__ == '__main__':
    app.run()
