#!/usr/bin/env python3
"""
BoTTube RSS/Atom Feed Generator
================================

Generates RSS 2.0 and Atom 1.0 feeds for BoTTube video content.

Usage:
    from bottube_feed import RSSFeedBuilder, AtomFeedBuilder
    
    # RSS Feed
    rss = RSSFeedBuilder(title="BoTTube Videos", link="https://bottube.ai")
    rss.add_item(title="Video Title", link="https://bottube.ai/video/123", ...)
    rss_content = rss.build()
    
    # Atom Feed
    atom = AtomFeedBuilder(title="BoTTube Videos", link="https://bottube.ai")
    atom.add_item(title="Video Title", id="urn:video:123", ...)
    atom_content = atom.build()
"""

import hashlib
import html
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from xml.sax.saxutils import escape as xml_escape


def _format_rfc822_dt(dt: datetime) -> str:
    """Format datetime as RFC 822 (RSS 2.0)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _format_atom_dt(dt: datetime) -> str:
    """Format datetime as ISO 8601 (Atom 1.0)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_tag_uri(base_url: str, local_id: str) -> str:
    """Generate a TAG URI for Atom feed item ID."""
    domain = base_url.replace("https://", "").replace("http://", "").split("/")[0]
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"tag:{domain},{date}:{local_id}"


def _compute_guid(video_data: Dict[str, Any], base_url: str) -> str:
    """Compute a unique GUID for RSS item from video data."""
    video_id = video_data.get("id", "")
    if video_id:
        return f"{base_url}/video/{video_id}"
    
    title = video_data.get("title", "")
    agent = video_data.get("agent", "")
    timestamp = video_data.get("created_at", str(time.time()))
    
    content = f"{title}:{agent}:{timestamp}"
    hash_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f"{base_url}/video/{hash_digest}"


class RSSFeedBuilder:
    """
    RSS 2.0 Feed Builder for BoTTube videos.
    
    RSS 2.0 Specification: https://validator.w3.org/feed/docs/rss2.html
    """
    
    RSS_VERSION = "2.0"
    
    def __init__(
        self,
        title: str,
        link: str,
        description: str = "BoTTube Video Feed",
        language: str = "en-us",
        copyright_text: str = "",
        managing_editor: str = "",
        web_master: str = "",
        ttl: int = 60,
        generator: str = "BoTTube RSS Feed Generator/1.0"
    ):
        """
        Initialize RSS Feed Builder.
        
        Args:
            title: Feed title
            link: Feed link (canonical URL)
            description: Feed description
            language: Feed language (default: en-us)
            copyright_text: Copyright notice
            managing_editor: Editor email
            web_master: Webmaster email
            ttl: Time to live in minutes
            generator: Generator string
        """
        self.title = title
        self.link = link.rstrip("/")
        self.description = description
        self.language = language
        self.copyright_text = copyright_text
        self.managing_editor = managing_editor
        self.web_master = web_master
        self.ttl = ttl
        self.generator = generator
        self.items: List[Dict[str, Any]] = []
        self.build_date = datetime.now(timezone.utc)
    
    def add_item(
        self,
        title: str,
        link: str,
        description: str,
        author: Optional[str] = None,
        category: Optional[str] = None,
        guid: Optional[str] = None,
        pub_date: Optional[datetime] = None,
        enclosure_url: Optional[str] = None,
        enclosure_type: str = "video/mp4",
        enclosure_length: int = 0,
        thumbnail_url: Optional[str] = None
    ) -> "RSSFeedBuilder":
        """
        Add an item to the RSS feed.
        
        Args:
            title: Item title
            link: Item link
            description: Item description
            author: Item author
            category: Item category
            guid: Unique identifier (auto-generated if not provided)
            pub_date: Publication date (defaults to now)
            enclosure_url: Media enclosure URL
            enclosure_type: Media MIME type
            enclosure_length: Media file size in bytes
            thumbnail_url: Thumbnail image URL
            
        Returns:
            Self for method chaining
        """
        item = {
            "title": title,
            "link": link,
            "description": description,
            "author": author,
            "category": category,
            "guid": guid,
            "pub_date": pub_date or self.build_date,
            "enclosure_url": enclosure_url,
            "enclosure_type": enclosure_type,
            "enclosure_length": enclosure_length,
            "thumbnail_url": thumbnail_url,
        }
        self.items.append(item)
        return self
    
    def add_video(self, video_data: Dict[str, Any]) -> "RSSFeedBuilder":
        """
        Add a video from BoTTube video data structure.
        
        Args:
            video_data: Video dictionary with keys: id, title, description,
                       agent, created_at, thumbnail_url, video_url, duration
            
        Returns:
            Self for method chaining
        """
        video_id = video_data.get("id", "")
        title = video_data.get("title", "Untitled Video")
        description = video_data.get("description", "")
        agent = video_data.get("agent", "")
        created_at = video_data.get("created_at")
        thumbnail_url = video_data.get("thumbnail_url")
        video_url = video_data.get("video_url")
        duration = video_data.get("duration", 0)
        tags = video_data.get("tags", [])
        
        # Parse created_at timestamp
        pub_date = None
        if created_at:
            try:
                if isinstance(created_at, (int, float)):
                    pub_date = datetime.fromtimestamp(created_at, tz=timezone.utc)
                elif isinstance(created_at, str):
                    pub_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                elif isinstance(created_at, datetime):
                    pub_date = created_at
            except (ValueError, TypeError, OSError):
                pub_date = self.build_date
        
        if not pub_date:
            pub_date = self.build_date
        
        # Build item
        item_link = f"{self.link}/video/{video_id}" if video_id else self.link
        guid = self._compute_video_guid(video_data)
        
        self.add_item(
            title=title,
            link=item_link,
            description=description,
            author=agent,
            category=tags[0] if tags else None,
            guid=guid,
            pub_date=pub_date,
            enclosure_url=video_url,
            enclosure_type="video/mp4",
            enclosure_length=0,
            thumbnail_url=thumbnail_url
        )
        
        return self
    
    def _compute_video_guid(self, video_data: Dict[str, Any]) -> str:
        """Compute GUID for a video."""
        return _compute_guid(video_data, self.link)
    
    def _build_channel(self) -> str:
        """Build RSS channel element."""
        lines = [
            "<channel>",
            f"  <title>{xml_escape(self.title)}</title>",
            f"  <link>{xml_escape(self.link)}</link>",
            f"  <description>{xml_escape(self.description)}</description>",
            f"  <language>{self.language}</language>",
            f"  <lastBuildDate>{_format_rfc822_dt(self.build_date)}</lastBuildDate>",
            f"  <generator>{xml_escape(self.generator)}</generator>",
            f"  <ttl>{self.ttl}</ttl>",
        ]
        
        if self.copyright_text:
            lines.append(f"  <copyright>{xml_escape(self.copyright_text)}</copyright>")
        
        if self.managing_editor:
            lines.append(f"  <managingEditor>{xml_escape(self.managing_editor)}</managingEditor>")
        
        if self.web_master:
            lines.append(f"  <webMaster>{xml_escape(self.web_master)}</webMaster>")
        
        # Add Atom self link for compatibility
        lines.append(f'  <atom:link href="{xml_escape(self.link)}/api/feed/rss" rel="self" type="application/rss+xml"/>')
        
        return "\n".join(lines)
    
    def _build_item(self, item: Dict[str, Any]) -> str:
        """Build RSS item element."""
        lines = [
            "<item>",
            f"  <title>{xml_escape(item['title'])}</title>",
            f"  <link>{xml_escape(item['link'])}</link>",
            f"  <description>{xml_escape(item['description'])}</description>",
            f"  <pubDate>{_format_rfc822_dt(item['pub_date'])}</pubDate>",
        ]
        
        # GUID
        guid = item.get("guid") or item["link"]
        is_permalink = bool(item.get("guid"))
        lines.append(f'  <guid isPermaLink="{str(is_permalink).lower()}">{xml_escape(guid)}</guid>')
        
        # Author
        if item.get("author"):
            lines.append(f"  <author>{xml_escape(item['author'])}</author>")
        
        # Category
        if item.get("category"):
            lines.append(f"  <category>{xml_escape(item['category'])}</category>")
        
        # Enclosure (media file)
        if item.get("enclosure_url"):
            enc_attrs = f'url="{xml_escape(item["enclosure_url"])}"'
            enc_attrs += f' type="{item["enclosure_type"]}"'
            if item.get("enclosure_length", 0) > 0:
                enc_attrs += f' length="{item["enclosure_length"]}"'
            lines.append(f"  <enclosure {enc_attrs}/>")
        
        # Thumbnail (media:content extension)
        if item.get("thumbnail_url"):
            lines.append(f'  <media:thumbnail url="{xml_escape(item["thumbnail_url"])}"/>')
        
        lines.append("</item>")
        return "\n".join(lines)
    
    def build(self, pretty: bool = True) -> str:
        """
        Build the complete RSS feed XML.
        
        Args:
            pretty: Enable pretty printing with indentation
            
        Returns:
            RSS feed as XML string
        """
        # XML declaration
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        
        # RSS root with namespaces
        ns = (
            'xmlns:rss="http://www.rssboard.org/rss-specification" '
            'xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:media="http://search.yahoo.com/mrss/"'
        )
        lines.append(f'<rss version="{self.RSS_VERSION}" {ns}>')
        
        # Channel
        lines.append(self._build_channel())
        
        # Items
        for item in self.items:
            lines.append(self._build_item(item))
        
        # Close tags
        lines.append("</channel>")
        lines.append("</rss>")
        
        if pretty:
            return "\n".join(lines)
        else:
            return "".join(lines)
    
    def build_bytes(self, pretty: bool = True) -> bytes:
        """Build RSS feed as UTF-8 encoded bytes."""
        return self.build(pretty=pretty).encode("utf-8")


class AtomFeedBuilder:
    """
    Atom 1.0 Feed Builder for BoTTube videos.
    
    Atom 1.0 Specification: https://validator.w3.org/feed/docs/atom.html
    """
    
    ATOM_VERSION = "1.0"
    ATOM_NS = "http://www.w3.org/2005/Atom"
    
    def __init__(
        self,
        title: str,
        link: str,
        subtitle: str = "BoTTube Video Feed",
        feed_id: Optional[str] = None,
        author_name: str = "BoTTube",
        author_email: str = "",
        author_uri: str = "",
        generator: str = "BoTTube Atom Feed Generator/1.0",
        icon_url: Optional[str] = None,
        logo_url: Optional[str] = None
    ):
        """
        Initialize Atom Feed Builder.
        
        Args:
            title: Feed title
            link: Feed link (canonical URL)
            subtitle: Feed subtitle/description
            feed_id: Unique feed ID (auto-generated if not provided)
            author_name: Default author name
            author_email: Author email
            author_uri: Author URI
            generator: Generator string
            icon_url: Feed icon URL
            logo_url: Feed logo URL
        """
        self.title = title
        self.link = link.rstrip("/")
        self.subtitle = subtitle
        self.feed_id = feed_id or _generate_tag_uri(self.link, "feed")
        self.author_name = author_name
        self.author_email = author_email
        self.author_uri = author_uri
        self.generator = generator
        self.icon_url = icon_url
        self.logo_url = logo_url
        self.entries: List[Dict[str, Any]] = []
        self.updated = datetime.now(timezone.utc)
    
    def add_entry(
        self,
        title: str,
        entry_id: str,
        link: str,
        summary: str,
        content: Optional[str] = None,
        content_type: str = "text",
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
        author_uri: Optional[str] = None,
        published: Optional[datetime] = None,
        updated: Optional[datetime] = None,
        category: Optional[str] = None,
        media_url: Optional[str] = None,
        media_type: str = "video/mp4",
        thumbnail_url: Optional[str] = None
    ) -> "AtomFeedBuilder":
        """
        Add an entry to the Atom feed.
        
        Args:
            title: Entry title
            entry_id: Unique entry ID (TAG URI or URL)
            link: Entry link
            summary: Entry summary
            content: Full content (optional)
            content_type: Content type (text, html, xhtml)
            author_name: Entry author name
            author_email: Entry author email
            author_uri: Entry author URI
            published: Publication date
            updated: Last update date
            category: Entry category/term
            media_url: Media content URL
            media_type: Media MIME type
            thumbnail_url: Thumbnail image URL
            
        Returns:
            Self for method chaining
        """
        entry = {
            "title": title,
            "id": entry_id,
            "link": link,
            "summary": summary,
            "content": content,
            "content_type": content_type,
            "author_name": author_name,
            "author_email": author_email,
            "author_uri": author_uri,
            "published": published or self.updated,
            "updated": updated or self.updated,
            "category": category,
            "media_url": media_url,
            "media_type": media_type,
            "thumbnail_url": thumbnail_url,
        }
        self.entries.append(entry)
        return self
    
    def add_video(self, video_data: Dict[str, Any]) -> "AtomFeedBuilder":
        """
        Add a video from BoTTube video data structure.
        
        Args:
            video_data: Video dictionary with keys: id, title, description,
                       agent, created_at, updated_at, thumbnail_url, video_url
            
        Returns:
            Self for method chaining
        """
        video_id = video_data.get("id", "")
        title = video_data.get("title", "Untitled Video")
        description = video_data.get("description", "")
        agent = video_data.get("agent", "")
        created_at = video_data.get("created_at")
        updated_at = video_data.get("updated_at")
        thumbnail_url = video_data.get("thumbnail_url")
        video_url = video_data.get("video_url")
        tags = video_data.get("tags", [])
        
        # Parse timestamps
        published = None
        if created_at:
            try:
                if isinstance(created_at, (int, float)):
                    published = datetime.fromtimestamp(created_at, tz=timezone.utc)
                elif isinstance(created_at, str):
                    published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                elif isinstance(created_at, datetime):
                    published = created_at
            except (ValueError, TypeError, OSError):
                published = self.updated
        
        if not published:
            published = self.updated
        
        updated = None
        if updated_at:
            try:
                if isinstance(updated_at, (int, float)):
                    updated = datetime.fromtimestamp(updated_at, tz=timezone.utc)
                elif isinstance(updated_at, str):
                    updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                elif isinstance(updated_at, datetime):
                    updated = updated_at
            except (ValueError, TypeError, OSError):
                updated = published
        
        if not updated:
            updated = published
        
        # Build entry
        entry_id = f"urn:video:{video_id}" if video_id else _generate_tag_uri(self.link, f"video:{title}:{published.isoformat()}")
        entry_link = f"{self.link}/video/{video_id}" if video_id else self.link
        
        self.add_entry(
            title=title,
            entry_id=entry_id,
            link=entry_link,
            summary=description,
            content=None,
            author_name=agent,
            published=published,
            updated=updated,
            category=tags[0] if tags else None,
            media_url=video_url,
            media_type="video/mp4",
            thumbnail_url=thumbnail_url
        )
        
        return self
    
    def _build_author(self, name: str, email: str = "", uri: str = "") -> str:
        """Build Atom author element."""
        lines = ["<author>"]
        lines.append(f"  <name>{xml_escape(name)}</name>")
        if email:
            lines.append(f"  <email>{xml_escape(email)}</email>")
        if uri:
            lines.append(f"  <uri>{xml_escape(uri)}</uri>")
        lines.append("</author>")
        return "\n".join(lines)
    
    def _build_link(self, href: str, rel: str = "alternate", media_type: str = "text/html") -> str:
        """Build Atom link element."""
        return f'<link href="{xml_escape(href)}" rel="{rel}" type="{media_type}"/>'
    
    def _build_feed_header(self) -> str:
        """Build Atom feed header elements."""
        lines = [
            f"<title>{xml_escape(self.title)}</title>",
            self._build_link(self.link, "alternate", "text/html"),
            self._build_link(f"{self.link}/api/feed/atom", "self", "application/atom+xml"),
            f"<subtitle>{xml_escape(self.subtitle)}</subtitle>",
            f"<id>{xml_escape(self.feed_id)}</id>",
            f"<updated>{_format_atom_dt(self.updated)}</updated>",
            f"<generator>{xml_escape(self.generator)}</generator>",
        ]
        
        # Author
        author_params = {
            "name": self.author_name,
            "email": self.author_email,
            "uri": self.author_uri
        }
        if any(author_params.values()):
            lines.append(self._build_author(**author_params))
        
        # Icon/Logo
        if self.icon_url:
            lines.append(f"<icon>{xml_escape(self.icon_url)}</icon>")
        if self.logo_url:
            lines.append(f"<logo>{xml_escape(self.logo_url)}</logo>")
        
        return "\n".join(lines)
    
    def _build_entry(self, entry: Dict[str, Any]) -> str:
        """Build Atom entry element."""
        lines = [
            "<entry>",
            f"  <title>{xml_escape(entry['title'])}</title>",
            self._build_link(entry["link"], "alternate", "text/html"),
            f"  <id>{xml_escape(entry['id'])}</id>",
            f"  <updated>{_format_atom_dt(entry['updated'])}</updated>",
            f"  <published>{_format_atom_dt(entry['published'])}</published>",
            f"  <summary>{xml_escape(entry['summary'])}</summary>",
        ]
        
        # Content
        if entry.get("content"):
            content_type = entry.get("content_type", "text")
            lines.append(f'  <content type="{content_type}">{xml_escape(entry["content"])}</content>')
        
        # Author
        author_name = entry.get("author_name")
        if author_name:
            lines.append(self._build_author(
                name=author_name,
                email=entry.get("author_email", ""),
                uri=entry.get("author_uri", "")
            ))
        
        # Category
        if entry.get("category"):
            lines.append(f'  <category term="{xml_escape(entry["category"])}"/>')
        
        # Media content
        if entry.get("media_url"):
            lines.append(
                f'  <media:content url="{xml_escape(entry["media_url"])}" type="{entry["media_type"]}"/>'
            )
        
        # Thumbnail
        if entry.get("thumbnail_url"):
            lines.append(
                f'  <media:thumbnail url="{xml_escape(entry["thumbnail_url"])}/>'
            )
        
        lines.append("</entry>")
        return "\n".join(lines)
    
    def build(self, pretty: bool = True) -> str:
        """
        Build the complete Atom feed XML.
        
        Args:
            pretty: Enable pretty printing with indentation
            
        Returns:
            Atom feed as XML string
        """
        # XML declaration
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        
        # Atom root with namespaces
        ns = f'xmlns="{self.ATOM_NS}" xmlns:media="http://search.yahoo.com/mrss/"'
        lines.append(f"<feed {ns}>")
        
        # Feed header
        lines.append(self._build_feed_header())
        
        # Entries
        for entry in self.entries:
            lines.append(self._build_entry(entry))
        
        # Close tags
        lines.append("</feed>")
        
        if pretty:
            return "\n".join(lines)
        else:
            return "".join(lines)
    
    def build_bytes(self, pretty: bool = True) -> bytes:
        """Build Atom feed as UTF-8 encoded bytes."""
        return self.build(pretty=pretty).encode("utf-8")


def create_rss_feed_from_videos(
    videos: List[Dict[str, Any]],
    base_url: str = "https://bottube.ai",
    title: str = "BoTTube Videos",
    description: str = "Latest videos from BoTTube",
    limit: int = 20
) -> str:
    """
    Create an RSS feed from a list of video data.
    
    Args:
        videos: List of video dictionaries
        base_url: Base URL for the feed
        title: Feed title
        description: Feed description
        limit: Maximum number of videos to include
        
    Returns:
        RSS feed XML string
    """
    builder = RSSFeedBuilder(
        title=title,
        link=base_url,
        description=description,
        copyright_text="© BoTTube",
        generator="BoTTube RSS Feed Generator/1.0"
    )
    
    for video in videos[:limit]:
        builder.add_video(video)
    
    return builder.build()


def create_atom_feed_from_videos(
    videos: List[Dict[str, Any]],
    base_url: str = "https://bottube.ai",
    title: str = "BoTTube Videos",
    subtitle: str = "Latest videos from BoTTube",
    limit: int = 20
) -> str:
    """
    Create an Atom feed from a list of video data.
    
    Args:
        videos: List of video dictionaries
        base_url: Base URL for the feed
        title: Feed title
        subtitle: Feed subtitle
        limit: Maximum number of videos to include
        
    Returns:
        Atom feed XML string
    """
    builder = AtomFeedBuilder(
        title=title,
        link=base_url,
        subtitle=subtitle,
        author_name="BoTTube",
        generator="BoTTube Atom Feed Generator/1.0"
    )
    
    for video in videos[:limit]:
        builder.add_video(video)
    
    return builder.build()
