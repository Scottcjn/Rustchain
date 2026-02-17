# RustChain.org SEO-Optimized Website

This directory contains an SEO-optimized website for RustChain with proper meta tags, structured data, and content pages optimized for search engines.

## 📋 Contents

### HTML Pages
- **index.html** - Main landing page with hero section and overview
- **about.html** - Comprehensive about page explaining Proof of Antiquity
- **mining.html** - Complete mining guide with installation instructions
- **tokenomics.html** - RTC token supply, distribution, and economics
- **hardware.html** - Hardware guide with multiplier tables
- **faq.html** - Frequently asked questions with structured data

### SEO Files
- **sitemap.xml** - Sitemap for search engine crawlers
- **robots.txt** - Robots.txt allowing all crawlers

### Assets
- **css/style.css** - Responsive CSS with dark terminal theme

## 🎯 SEO Features

### 1. HTML Meta Tags
All pages include comprehensive meta tags:
- `<title>` with keywords
- `<meta name="description">` for search snippets
- `<meta name="keywords">` for discoverability
- `<meta name="robots">` with index/follow directives

### 2. Open Graph Tags
Social media optimization:
- Open Graph for Facebook/LinkedIn
- Twitter Cards for Twitter
- Proper og:image tags for share previews

### 3. Structured Data (JSON-LD)
Google-rich results with:
- Organization schema
- SoftwareApplication schema (for clawrtc)
- FAQPage schema (FAQ page only)
- WebPage schema (other pages)

### 4. Canonical URLs
Prevents duplicate content issues with `<link rel="canonical">`.

### 5. Technical SEO
- sitemap.xml listing all pages
- robots.txt allowing crawlers
- Internal linking between pages
- Semantic HTML structure
- Mobile-responsive design

## 🚀 Deployment

### Local Testing
```bash
cd web-seo
python3 -m http.server 8080
# Visit http://localhost:8080
```

### Production Deployment
```bash
# Copy files to web server
sudo cp -r web-seo/* /var/www/rustchain-org/

# Or deploy to static hosting
# Netlify, Vercel, GitHub Pages, etc.
```

### Nginx Configuration
Add to nginx config:
```nginx
server {
    listen 80;
    server_name rustchain.org;

    root /var/www/rustchain-org;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # Serve sitemap
    location = /sitemap.xml {
        root /var/www/rustchain-org;
    }

    # Serve robots.txt
    location = /robots.txt {
        root /var/www/rustchain-org;
    }
}
```

## 📊 Content Overview

### Page Word Counts (SEO-optimized)
- index.html: ~1,200 words
- about.html: ~850 words
- mining.html: ~1,100 words
- tokenomics.html: ~700 words
- hardware.html: ~900 words
- faq.html: ~1,500 words

### Keyword Density
Target keywords naturally integrated:
- "RustChain" - Primary keyword
- "vintage hardware mining" - Main topic
- "PowerPC", "68K", "SPARC" - Hardware types
- "proof of antiquity" - Consensus mechanism
- "RTC token", "cryptocurrency" - Token keywords

### Internal Linking
Pages are cross-linked for SEO:
- Footer navigation to all pages
- Content links to related pages
- CTA sections linking to guides

## 🔍 Search Engine Optimization

### Google Search Console
Submit sitemap:
1. Go to Google Search Console
2. Add property: https://rustchain.org
3. Submit sitemap.xml

### Bing Webmaster Tools
Same process for Bing:
1. Go to Bing Webmaster Tools
2. Add property
3. Submit sitemap.xml

### Page Speed Optimization
- CSS minified and inlined where appropriate
- No external blocking scripts
- Optimized images (add alt tags)
- Lazy loading for large content (future)

## 📈 Monitoring

### Track Rankings
Monitor for these keywords:
- "vintage hardware mining"
- "RustChain crypto"
- "PowerPC mining"
- "68K Macintosh cryptocurrency"
- "proof of antiquity blockchain"

### Tools
- Google Search Console - Performance and indexing
- Google Analytics - Traffic sources
- PageSpeed Insights - Performance scores
- Ahrefs/SEMrush - Backlinks and rankings

## 🎨 Customization

### Branding
Update these in HTML files:
- Site name in `<title>` tags
- Organization name in JSON-LD
- Contact information
- Social media links

### Content
All content is in HTML files. Edit to:
- Add new FAQ items
- Update tokenomics information
- Add more hardware types
- Update statistics and numbers

## 📦 Directory Structure
```
web-seo/
├── index.html          # Main landing page
├── about.html          # About RustChain
├── mining.html         # Mining guide
├── tokenomics.html     # Token economics
├── hardware.html       # Hardware guide
├── faq.html            # FAQ page
├── sitemap.xml         # Search engine sitemap
├── robots.txt          # Crawler instructions
├── css/
│   └── style.css      # Styling
├── js/                 # JavaScript (future)
└── images/             # Images and icons (add yours)
```

## 🔄 Updates

### Regular Updates Required
1. **Statistics** - Update epoch, miners, attestations in index.html
2. **FAQ** - Add new common questions
3. **Hardware** - Add newly supported hardware
4. **Tokenomics** - Update supply and distribution if changed

### Sitemap Last Modified
Update `<lastmod>` dates in sitemap.xml when content changes.

## 📞 Support

For questions or issues:
- GitHub: https://github.com/Scottcjn/Rustchain/issues
- Email: [add contact email]
- Discord: [RustChain Discord]

## 📄 License

Same as RustChain project.
