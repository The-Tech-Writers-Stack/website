from pathlib import Path
from typing import Tuple, List
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, send_file
from markupsafe import Markup
import requests
import collections
from .crawl import get_data, latest_articles, new_members
from tenacity import retry, wait_random_exponential, stop_after_attempt
import shelve


app = Flask(__name__)


@app.route("/favicon.ico")
def favicon():
    return send_file(Path(__file__).parent / "favicon.ico")


@app.route("/<string:substack_name>/<string:post_url_path>")
def redirect_post(substack_name: str, post_url_path: str):
    with shelve.open("clicks.db", flag="c") as db:
        key = f"{substack_name}/{post_url_path}"
        db[key] = db.get(key, 0) + 1
        db[substack_name] = db.get(substack_name, 0) + 1

    substack_url = f'https://{substack_name}.substack.com/p/{post_url_path}'
    title, meta = get_title_and_meta_tags(substack_url)
    return render_template('empty.html', title=title, meta_tag_list=meta, url=substack_url)


@app.route("/<string:substack_name>")
def redirect_substack(substack_name: str):
    with shelve.open("clicks.db", flag="c") as db:
        db[substack_name] = db.get(substack_name, 0) + 1

    substack_url = f'https://{substack_name}.substack.com'
    title, meta = get_title_and_meta_tags(substack_url)
    return render_template('empty.html', title=title, meta_tag_list=meta, url=substack_url)


@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def get_title_and_meta_tags(url: str) -> Tuple[str, List[str]]:
    # Send a GET request to the URL
    response = requests.get(url)

    # Create a BeautifulSoup object to parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the title tag
    title_tag = soup.find('title')

    # Find all meta tags within the page
    meta_tags = soup.find_all('meta')
    title_tag_safe = Markup(str(title_tag))
    meta_tags_safe = [Markup(str(meta_tag)) for meta_tag in meta_tags]

    # Return the title tag and meta tags
    return title_tag_safe, meta_tags_safe


@app.route("/")
def index():
    filters = request.args.get('filter')

    data = get_data()
    latest = latest_articles(3, 30)

    if filters:
        print(filters, flush=True)
        data = [website for website in data if filters in set(website['topics'])]

    return render_template('index.html', data=data, latest=latest, filters=filters)


@app.route("/admin")
def admin():

    data = get_data()
    new = new_members(data)
    latest = latest_articles()

    by_authors = collections.defaultdict(list)

    for article in latest:
        by_authors[(article['author'], article['url'])].append(article)

    return render_template('admin.html', data=data, new_members=new, latest=by_authors)
