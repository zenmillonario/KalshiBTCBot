"""Optional Chromium component checks with a caller-supplied, real adapter snapshot.

Usage: python nautilus/tests/browser_checks.py /path/to/snapshot.json /output/folder
Requires Playwright + Chromium in the developer environment, not on the user's PC.
The browser is fully offline: same-origin fetch is fulfilled by the provided snapshot.
HTTP transport/security is tested separately by test_nautilus.py.
"""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    snapshot=Path(sys.argv[1]);output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
    state=json.loads(snapshot.read_text());root=Path(__file__).resolve().parents[1]/'static'
    checks=[]
    def check(name,condition):
        assert condition,name
        checks.append(name)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1672,'height':1060},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        html=(root/'index.html').read_text().replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/chart.js" defer></script><script src="/app.js" defer></script>','')
        page.set_content(html);page.add_style_tag(content=(root/'style.css').read_text())
        page.evaluate('(s)=>{window.__fixture=s;window.fetch=async()=>({ok:true,json:async()=>structuredClone(window.__fixture)});}',state)
        page.add_script_tag(content=(root/'chart.js').read_text());page.add_script_tag(content=(root/'app.js').read_text())
        page.wait_for_function('window.__nautilus && window.__nautilus.state');page.wait_for_timeout(400)
        check('No script errors on initial recorded run',not errors)
        check('Exact 45-minute default viewport',page.evaluate('__nautilus.chart.span===2700'))
        check('Stopped archive is not a running timer',page.locator('#timerValue').inner_text()=='ARCHIVE')
        check('Before-fee canonical total appears to two decimals',page.locator('#realizedValue').inner_text()=='+$45.70')
        check('Original engine feed appears',page.locator('.feed-line').count()>10)
        check('Desktop has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=str(output/'Nautilus_recorded_monitor.png'),full_page=True)
        canvas=page.locator('#marketChart');box=canvas.bounding_box()
        start=page.evaluate('__nautilus.chart.end')
        page.mouse.move(box['x']+400,box['y']+180);page.mouse.down();page.mouse.move(box['x']+580,box['y']+180,steps=5);page.mouse.up()
        panned=page.evaluate('__nautilus.chart.end')
        check('Dragging detaches following and pans history',page.evaluate('!__nautilus.chart.follow') and panned<start)
        page.wait_for_timeout(1300)
        check('Polling does not snatch the panned viewport',page.evaluate('__nautilus.chart.end')==panned)
        page.mouse.move(box['x']+400,box['y']+180);page.mouse.wheel(0,-160);page.wait_for_timeout(100)
        span=page.evaluate('__nautilus.chart.span')
        check('Wheel zoom changes candle spacing',span<2700)
        page.wait_for_timeout(1200);check('Zoom survives a data update',page.evaluate('__nautilus.chart.span')==span)
        page.locator('#spanSelect').select_option('45');page.locator('#liveEdge').click()
        old=page.evaluate('__nautilus.chart.end')
        page.evaluate('''()=>{const s=structuredClone(__fixture),b={...s.candles.at(-1)};b.time+=60;s.candles.push(b);s.market.ticker='ROLLOVER_TEST';__nautilus.chart.setData(s);}''')
        check('Live edge advances on next candle without changing span',page.evaluate('__nautilus.chart.end')==old+60 and page.evaluate('__nautilus.chart.span')==2700)
        page.evaluate('__nautilus.chart.setData(__fixture)')
        # A known recorded winner is used only for a review screenshot, never as a live result.
        page.evaluate('''()=>{const t=__fixture.trades.find(x=>x.trade_id==='23');__nautilus.chart.onSelect(t);}''')
        check('Trade selection switches review and matches evidence', 'Trade #23' in page.locator('#detailsTitle').inner_text() and page.locator('#reviewMode').get_attribute('class')=='active')
        page.wait_for_timeout(500)
        page.screenshot(path=str(output/'Nautilus_recorded_review.png'),full_page=True)
        if page.locator('#pauseFeed').get_attribute('aria-pressed')!='true':page.locator('#pauseFeed').click()
        original_count=page.locator('.feed-line').count()
        page.evaluate("__fixture.feed.push({id:'ui-test-message',text:'<img src=x onerror=alert(1)> TEST MESSAGE',category:'trade'})")
        page.wait_for_timeout(1300)
        check('Paused feed remains readable while new lines arrive',page.locator('.feed-line').count()==original_count and '1 new' in page.locator('#newLines').inner_text())
        page.locator('#pauseFeed').click();page.wait_for_timeout(100)
        check('Feed resumes without interpreting engine markup',page.locator('#engineFeed img').count()==0 and '<img' in page.locator('.feed-line').last.inner_text())
        page.locator('#healthButton').click();check('Source integrity dialog opens',page.locator('#healthDialog').evaluate('(d)=>d.open'));page.locator('#closeHealth').click()
        page.set_viewport_size({'width':900,'height':1050});page.wait_for_timeout(100)
        check('Tablet layout has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.set_viewport_size({'width':420,'height':950});page.wait_for_timeout(100)
        check('Small-screen layout has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.set_viewport_size({'width':1672,'height':1060})
        # Synthetic live fixture validates instruments, not a real live trading session.
        page.evaluate("""()=>{const s=__fixture,n=Date.now()/1000;s.server_now=n;s.run={...s.run,review:false,stopped:false,fresh:true,updated:n};s.market={...s.market,time:n,fresh:true,close_ts:n+577};s.quote={...s.quote,fresh:true,yes_bid:.4,yes_ask:.42,no_bid:.58,no_ask:.6,valid_until:n+10};}""")
        page.wait_for_timeout(1250)
        check('Live fixture displays large countdown and native quotes',page.locator('#timerValue').inner_text().startswith('09:') and page.locator('#yesQuote').inner_text()=='0.400 / 0.420')
        check('Live fixture distinguishes updating PAPER feed',page.locator('#connection').inner_text()=='FEED CONNECTED' and 'PAPER' in page.locator('.badge.paper').inner_text())
        # Feed-loss test: finite last-recorded prices must not masquerade as current quotes.
        page.evaluate("()=>{window.fetch=async()=>{throw new Error('TEST CONNECTION LOSS')};}")
        page.wait_for_timeout(1400)
        check('Connection loss visibly clears current quote instruments',page.locator('#connection').inner_text()=='DISCONNECTED' and page.locator('#yesQuote').inner_text()=='— / —' and page.locator('#errorBanner').is_visible())
        check('No browser script exceptions in interaction tests',not errors)
        browser.close()
    report={'checks_passed':len(checks),'checks':checks,'browser_errors':errors,'source':snapshot.name,'method':'Offline Chromium component tests using real adapter snapshot; synthetic append/rollover/failure cases are explicitly test-only.'}
    (output/'browser_validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
