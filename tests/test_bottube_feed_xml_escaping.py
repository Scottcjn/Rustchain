# SPDX-License-Identifier: MIT
"""Regression tests for BoTTube RSS/Atom XML attribute escaping and null guards."""

import sqlite3
import sys
from pathlib import Path

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET  # nosec B405 - parses test-generated XML

from flask import Flask

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "node") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "node"))

from bottube_feed import (
    AtomFeedBuilder,
    RSSFeedBuilder,
    create_atom_feed_from_videos,
    create_rss_feed_from_videos,
)
from bottube_feed_routes import feed_bp

ATOM_NS = "{http://www.w3.org/2005/Atom}"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"


def test_rss_escapes_xml_attributes_and_stays_well_formed():
    injected_url = 'https://example.com/a.mp4" evil="1" x=\'<tag>'
    injected_thumb = 'https://example.com/t.jpg" onload="alert(1)'
    injected_type = 'video/mp4" bogus="x'
    injected_base = 'https://example.com/base" injected="true'

    builder = RSSFeedBuilder(
        title='Feed "Title" & <More>',
        link=injected_base,
        description="Channel <desc> & 'quotes'",
        language='en-us"bad="1',
    )
    builder.add_item(
        title='Item "Title" <x>',
        link='https://example.com/v/1"bad="2',
        description="Body & <xml>",
        author='agent"1',
        category='cat"1',
        enclosure_url=injected_url,
        enclosure_type=injected_type,
        enclosure_length=512,
        thumbnail_url=injected_thumb,
    )

    xml_text = builder.build()
    root = ET.fromstring(xml_text)  # nosec B314 - parses own builder output

    channel = root.find("channel")
    assert channel is not None
    atom_self = channel.find(f"{ATOM_NS}link")
    assert atom_self is not None
    assert "injected" not in atom_self.attrib
    assert atom_self.attrib["href"] == f"{injected_base}/api/feed/rss"

    item = channel.find("item")
    assert item is not None
    enclosure = item.find("enclosure")
    assert enclosure is not None
    assert set(enclosure.attrib.keys()) == {"url", "type", "length"}
    assert enclosure.attrib["url"] == injected_url
    assert enclosure.attrib["type"] == injected_type
    assert enclosure.attrib["length"] == "512"

    thumb = item.find(f"{MEDIA_NS}thumbnail")
    assert thumb is not None
    assert set(thumb.attrib.keys()) == {"url"}
    assert thumb.attrib["url"] == injected_thumb


def test_atom_escapes_xml_attributes_and_stays_well_formed():
    injected_cat = 'retro" injected="yes'
    injected_media = 'https://example.com/v.mp4" bad="1'
    injected_thumb = 'https://example.com/t.jpg" bad="2'
    injected_ctype = 'text" bad="3'
    injected_mtype = 'video/mp4" bad="4'

    builder = AtomFeedBuilder(
        title='Atom "Feed"',
        link='https://example.com/feed" x="1',
        subtitle="Sub <title>",
    )
    builder.add_entry(
        title="Entry 1",
        entry_id="urn:video:1",
        link='https://example.com/video/1" extra="1',
        summary="Summary",
        content="Body <text>",
        content_type=injected_ctype,
        author_name="bot-1",
        category=injected_cat,
        media_url=injected_media,
        media_type=injected_mtype,
        thumbnail_url=injected_thumb,
    )

    xml_text = builder.build()
    root = ET.fromstring(xml_text)  # nosec B314 - parses own builder output

    entry = root.find(f"{ATOM_NS}entry")
    assert entry is not None

    link_el = entry.find(f"{ATOM_NS}link")
    assert link_el is not None
    assert "extra" not in link_el.attrib

    content_el = entry.find(f"{ATOM_NS}content")
    assert content_el is not None
    assert set(content_el.attrib.keys()) == {"type"}
    assert content_el.attrib["type"] == injected_ctype

    cat_el = entry.find(f"{ATOM_NS}category")
    assert cat_el is not None
    assert set(cat_el.attrib.keys()) == {"term"}
    assert cat_el.attrib["term"] == injected_cat

    media_el = entry.find(f"{MEDIA_NS}content")
    assert media_el is not None
    assert set(media_el.attrib.keys()) == {"url", "type"}
    assert media_el.attrib["url"] == injected_media
    assert media_el.attrib["type"] == injected_mtype

    thumb_el = entry.find(f"{MEDIA_NS}thumbnail")
    assert thumb_el is not None
    assert set(thumb_el.attrib.keys()) == {"url"}
    assert thumb_el.attrib["url"] == injected_thumb


def test_builders_handle_null_db_fields_without_crashing():
    null_video = {
        "id": None,
        "title": None,
        "description": None,
        "agent": None,
        "created_at": None,
        "updated_at": None,
        "thumbnail_url": None,
        "video_url": None,
        "tags": None,
    }

    rss_xml = create_rss_feed_from_videos([null_video], base_url="https://bottube.ai")
    rss_root = ET.fromstring(rss_xml)  # nosec B314 - parses own builder output
    rss_title = rss_root.find("./channel/item/title")
    assert rss_title is not None
    assert rss_title.text == "Untitled Video"

    atom_xml = create_atom_feed_from_videos([null_video], base_url="https://bottube.ai")
    atom_root = ET.fromstring(atom_xml)  # nosec B314 - parses own builder output
    atom_title = atom_root.find(f"{ATOM_NS}entry/{ATOM_NS}title")
    assert atom_title is not None
    assert atom_title.text == "Untitled Video"

    rss_none_link = RSSFeedBuilder(title=None, link=None, description=None).add_item(
        title=None, link=None, description=None
    ).build()
    assert ET.fromstring(rss_none_link) is not None  # nosec B314

    atom_none_link = AtomFeedBuilder(title=None, link=None, subtitle=None).add_entry(
        title=None, entry_id=None, link=None, summary=None
    ).build()
    assert ET.fromstring(atom_none_link) is not None  # nosec B314


def test_builders_strip_illegal_xml_control_characters():
    video = {
        "id": "ctrl\x00-1",
        "title": "Clean\x00Title\x07\x1f!",
        "description": "Line1\nLine2\x0b\x0c\x08",
        "agent": "bot\x001",
        "thumbnail_url": "https://example.com/t\x00.jpg",
        "video_url": "https://example.com/v\x07.mp4",
        "tags": ["tag\x00one"],
    }

    rss_root = ET.fromstring(create_rss_feed_from_videos([video]))  # nosec B314
    assert rss_root.find("./channel/item/title").text == "CleanTitle!"

    atom_root = ET.fromstring(create_atom_feed_from_videos([video]))  # nosec B314
    assert atom_root.find(f"{ATOM_NS}entry/{ATOM_NS}title").text == "CleanTitle!"


def test_add_video_extracts_first_tag_from_json_string_and_list():
    videos = [
        {"id": "v1", "title": "JSON Tags", "tags": '["mining", "retro"]'},
        {"id": "v2", "title": "List Tags", "tags": ["ai", "demo"]},
        {"id": "v3", "title": "Empty Tags", "tags": []},
        {"id": "v4", "title": "Null Tags", "tags": None},
    ]

    rss_root = ET.fromstring(create_rss_feed_from_videos(videos))  # nosec B314
    rss_cats = [
        item.find("category").text if item.find("category") is not None else None
        for item in rss_root.findall("./channel/item")
    ]
    assert rss_cats == ["mining", "ai", None, None]

    atom_root = ET.fromstring(create_atom_feed_from_videos(videos))  # nosec B314
    atom_cats = [
        entry.find(f"{ATOM_NS}category").attrib["term"]
        if entry.find(f"{ATOM_NS}category") is not None
        else None
        for entry in atom_root.findall(f"{ATOM_NS}entry")
    ]
    assert atom_cats == ["mining", "ai", None, None]


def test_feed_routes_render_valid_xml_with_null_and_quote_db_rows(tmp_path):
    db_path = tmp_path / "feeds.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE bottube_videos (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            agent TEXT,
            created_at INTEGER,
            updated_at INTEGER,
            thumbnail_url TEXT,
            video_url TEXT,
            tags TEXT,
            public INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        INSERT INTO bottube_videos
        (id, title, description, agent, created_at, thumbnail_url, video_url, tags, public)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            "row-null",
            None,
            None,
            None,
            1700000000,
            None,
            None,
            None,
        ),
    )
    conn.execute(
        """
        INSERT INTO bottube_videos
        (id, title, description, agent, created_at, thumbnail_url, video_url, tags, public)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            "row-quotes",
            'Quoted\x00 "Title" <1>',
            'Desc & "Quotes"',
            'agent"x',
            1700000100,
            'https://example.com/thumb.jpg" evil="1',
            'https://example.com/vid.mp4" evil="2',
            '["tag\\"1", "second"]',
        ),
    )
    conn.commit()
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(feed_bp)
    client = app.test_client()

    rss_resp = client.get("/api/feed/rss")
    assert rss_resp.status_code == 200
    rss_root = ET.fromstring(rss_resp.get_data(as_text=True))  # nosec B314
    assert len(rss_root.findall("./channel/item")) == 2

    atom_resp = client.get("/api/feed/atom")
    assert atom_resp.status_code == 200
    atom_root = ET.fromstring(atom_resp.get_data(as_text=True))  # nosec B314
    assert len(atom_root.findall(f"{ATOM_NS}entry")) == 2
