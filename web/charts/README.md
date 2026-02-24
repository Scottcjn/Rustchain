# RTC TradingView-Style Widget

File: `web/charts/rtc-price-widget.html`

## Features
- Embeddable widget via iframe
- Interactive zoom/pan (Lightweight Charts)
- Active miners trend
- Epoch reward history
- RTC transfer volume proxy over time

## Use
Open directly in browser, optionally with custom API endpoint:

```bash
python3 -m http.server 8080
# then open:
# http://localhost:8080/web/charts/rtc-price-widget.html
```

Custom API endpoint query:
`rtc-price-widget.html?api=https://50.28.86.131`

## Embed
```html
<iframe src="https://your-host/web/charts/rtc-price-widget.html" width="100%" height="700" frameborder="0"></iframe>
```
