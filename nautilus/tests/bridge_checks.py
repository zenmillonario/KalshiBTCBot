"""Offline Chromium UI acceptance tests for Bridge 1.1.

Usage: python bridge_checks.py RECORDED_ADAPTER_SNAPSHOT.json OUTPUT_DIRECTORY
Requires developer-only playwright/chromium. Does not connect to a trading engine.
HTTP security/transport is tested separately by test_nautilus.py. Managed Chromium
blocks local navigation here, so exact assets are mounted with set_content and the
fetch response is a supplied real archived snapshot. Persistence uses a storage shim.
"""
import json
import os
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    data=json.loads(Path(sys.argv[1]).read_text())
    output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
    static=Path(__file__).resolve().parents[1]/'static'
    checks=[];errors=[]
    def check(name,result):
        assert result,name
        checks.append(name)
        print('PASS',name,flush=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1664,'height':806},device_scale_factor=1)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        def mount(storage=None):
            html=(static/'index.html').read_text()
            html=re.sub(r'<link[^>]+>','',html)
            html=re.sub(r'<script.*?</script>','',html)
            page.set_content(html)
            for name in ['style.css','bridge.css']:page.add_style_tag(content=(static/name).read_text())
            page.evaluate('''({data,saved})=>{
              window.__fixture=structuredClone(data);
              const store=new Map(Object.entries(saved||{}));
              Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k),clear:()=>store.clear()}});
              window.fetch=async()=>({ok:true,json:async()=>structuredClone(window.__fixture)});
            }''',{'data':data,'saved':storage})
            for name in ['chart.js','app.js','bridge.js']:page.add_script_tag(content=(static/name).read_text())
            page.wait_for_function('window.__nautilus?.display && window.__nautilus.state')
            page.wait_for_timeout(100)
        mount()
        def rects():
            return page.evaluate('''()=>Object.fromEntries(['.operations','.feed-panel','.trades-panel','.chart-panel','.intelligence-rail','.workspace'].map(s=>{const n=document.querySelector(s),r=n.getBoundingClientRect();return[s,{x:r.x,y:r.y,w:r.width,h:r.height,bottom:r.bottom,right:r.right}]}))''')
        def fits():return page.evaluate('document.documentElement.scrollHeight<=innerHeight+1 && document.documentElement.scrollWidth<=innerWidth+1')
        check('No initial browser exceptions',not errors)
        check('1664px TV screenshot viewport resolves to Bridge',page.get_attribute('body','data-layout')=='bridge')
        r=rects();check('Left activity, centered chart, right intelligence ordering',r['.operations']['right']<r['.chart-panel']['x'] and r['.chart-panel']['right']<r['.intelligence-rail']['x'])
        check('Feed and trades above the fold at 1664 x 806',all(r[k]['h']>150 and r[k]['bottom']<=806 for k in ['.feed-panel','.trades-panel']))
        check('TV layout has no page overflow',fits())
        check('Recorded gross total remains canonical',page.locator('#realizedValue').inner_text()=='+$45.70')
        check('Chart remains 45 minutes',page.evaluate('__nautilus.chart.span===2700'))
        page.screenshot(path=str(output/'Nautilus_v1_1_Bridge.png'),full_page=True)
        page.click('[data-tab="decisions"]')
        check('Decision table accessible in left rail without page scroll','REASON' in page.locator('#tableArea').inner_text() and page.locator('.feed-panel').is_visible())
        page.click('[data-tab="trades"]')
        page.locator('#tableArea').evaluate('(e)=>{e.scrollTop=250;e.scrollLeft=8;}')
        before=page.locator('#tableArea').evaluate('(e)=>e.scrollTop');page.wait_for_timeout(1200)
        check('Trade-table scroll survives updates',page.locator('#tableArea').evaluate('(e)=>e.scrollTop')==before)
        page.locator('#tableArea').evaluate('(e)=>e.scrollTop=0')
        page.locator('#pauseFeed').click()
        count=page.locator('.feed-line').count()
        page.evaluate("__fixture.feed.push({id:'bridge-test-line',text:'ENTRY | <img src=x> test-only',category:'trade'})")
        page.wait_for_timeout(1200)
        check('Paused console holds text while new records arrive',page.locator('.feed-line').count()==count and '1 new' in page.locator('#newLines').inner_text())
        page.locator('#pauseFeed').click()
        check('Feed resumes and text does not become HTML',page.locator('#engineFeed img').count()==0 and '<img' in page.locator('.feed-line').last.inner_text())
        page.evaluate("__fixture.feed.pop()")
        page.evaluate("__nautilus.chart.onSelect(__fixture.trades.find(t=>t.trade_id==='23'))")
        check('Trade selection opens briefing/review on right',page.get_attribute('body','data-right')=='briefing' and page.locator('#briefingPanel').is_visible() and 'Trade #23' in page.locator('#detailsTitle').inner_text())
        page.screenshot(path=str(output/'Nautilus_v1_1_Review.png'),full_page=True)
        page.click('#liveMode')
        check('Monitor restores position and protection rail',page.locator('#positionsPanel').is_visible() and page.locator('#protectionPanel').is_visible())
        box=page.locator('#marketChart').bounding_box()
        page.mouse.move(box['x']+250,box['y']+110);page.mouse.down();page.mouse.move(box['x']+330,box['y']+110,steps=4);page.mouse.up()
        end=page.evaluate('__nautilus.chart.end');page.wait_for_timeout(1200)
        check('Panned chart does not jump on refresh',not page.evaluate('__nautilus.chart.follow') and page.evaluate('__nautilus.chart.end')==end)
        page.click('#zoomIn');span=page.evaluate('__nautilus.chart.span');check('Touch-sized zoom buttons change time scale',span<2700)
        page.click('#displaySettings');page.select_option('#readability','1.3');page.click('#closeDisplay');page.wait_for_timeout(100)
        check('Text scaling preserves inspected chart time and zoom',page.evaluate('__nautilus.chart.end')==end and page.evaluate('__nautilus.chart.span')==span)
        check('Extra-large text keeps feed and trades above fold',fits() and rects()['.trades-panel']['bottom']<=806)
        saved=page.evaluate("localStorage.getItem('nautilus.display.v1.1')")
        check('Display preference serializes scale',json.loads(saved)['scale']==1.3)
        page.click('#displaySettings');page.click('#resetDisplay');page.click('#closeDisplay');page.select_option('#spanSelect','45');page.click('#liveEdge')
        old=page.evaluate('__nautilus.chart.end')
        page.evaluate("()=>{const s=structuredClone(__fixture),b={...s.candles.at(-1)};b.time+=60;s.candles.push(b);s.market.ticker='ROLLOVER_TEST';__nautilus.chart.setData(s);}")
        check('Rollover append advances chart without resetting span',page.evaluate('__nautilus.chart.end')==old+60 and page.evaluate('__nautilus.chart.span')==2700)
        page.evaluate('__nautilus.chart.setData(__fixture)')
        page.click('#bridgeFullscreen');page.wait_for_timeout(150)
        check('Whole dashboard fullscreen enters from button',page.evaluate('document.fullscreenElement===document.documentElement'))
        check('Whole fullscreen retains feed trades and positions',page.locator('.feed-panel').is_visible() and page.locator('.trades-panel').is_visible() and page.locator('#positionsPanel').is_visible())
        page.click('#bridgeFullscreen');check('Whole fullscreen exits from button',page.evaluate('!document.fullscreenElement'))
        page.click('#fullChart');page.wait_for_timeout(100)
        check('Chart-only fullscreen is independent',page.evaluate('document.fullscreenElement?.id==="chartPanel"'))
        page.click('#fullChart');check('Chart fullscreen returns to bridge',page.evaluate('!document.fullscreenElement') and page.locator('.feed-panel').is_visible())
        page.evaluate("()=>{window.__savedRequest=document.documentElement.requestFullscreen;document.documentElement.requestFullscreen=undefined}")
        page.click('#bridgeFullscreen');check('Unsupported fullscreen has visible fallback',page.locator('#displayNotice').is_visible() and 'F11' in page.locator('#displayNotice').inner_text())
        page.evaluate('()=>{document.documentElement.requestFullscreen=window.__savedRequest;}')
        page.locator('#displayNotice').evaluate("e=>e.classList.add('hidden')")
        for w,h in [(1920,1080),(1366,768),(1280,720),(3840,2160)]:
            page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(100)
            check(f'Wide viewport {w}x{h} fits without page scroll',fits())
            r=rects();check(f'Feed and trades stay visible at {w}x{h}',page.locator('.feed-panel').is_visible() and page.locator('.trades-panel').is_visible() and r['.trades-panel']['bottom']<=h)
        page.set_viewport_size({'width':1024,'height':768});page.wait_for_timeout(100)
        check('Tablet landscape uses chart plus dock',page.get_attribute('body','data-layout')=='tablet' and fits() and page.locator('.chart-panel').is_visible() and page.locator('.feed-panel').is_visible())
        page.locator('[data-deck="decisions"]').click()
        check('Tablet Decisions shows table alongside chart',page.locator('.trades-panel').is_visible() and page.locator('.chart-panel').is_visible() and 'REASON' in page.locator('#tableArea').inner_text())
        page.locator('[data-deck="positions"]').click();page.screenshot(path=str(output/'Nautilus_v1_1_Tablet.png'),full_page=True)
        check('Tablet Positions shows both position/protection',page.locator('#positionsPanel').is_visible() and page.locator('#protectionPanel').is_visible())
        page.set_viewport_size({'width':768,'height':1024});page.wait_for_timeout(100)
        check('Portrait tablet remains viewport fitted',fits())
        r=rects();check('Portrait tablet places dock below chart',r['.intelligence-rail']['y']>=r['.chart-panel']['bottom'])
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(100)
        check('Phone layout resolves automatically',page.get_attribute('body','data-layout')=='mobile' and fits())
        check('Phone starts on a full-width chart',page.locator('.chart-panel').is_visible() and not page.locator('.operations').is_visible())
        page.screenshot(path=str(output/'Nautilus_v1_1_Phone.png'),full_page=True)
        check('Phone branding is not squeezed',page.locator('.brand h1').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'))
        check('Phone main price numbers not clipped',page.evaluate("['targetValue','btcValue','timerValue'].every(id=>{let e=document.getElementById(id);return e.scrollWidth<=e.clientWidth+1})"))
        for deck,selector in [('feed','.feed-panel'),('trades','.trades-panel'),('decisions','.trades-panel'),('positions','#positionsPanel'),('briefing','#briefingPanel'),('chart','.chart-panel')]:
            page.locator(f'button[data-deck="{deck}"]').click();page.wait_for_timeout(60)
            check(f'Phone {deck} is reachable and visible',page.locator(selector).is_visible() and fits())
        page.select_option('#spanSelect','45')
        box=page.locator('#marketChart').bounding_box()
        session=context.new_cdp_session(page)
        def points(distance):
            return [{'x':box['x']+80,'y':box['y']+90,'id':11}, {'x':box['x']+80+distance,'y':box['y']+90,'id':12}]
        session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':points(70)[:1]})
        session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':points(70)})
        session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':points(140)})
        page.wait_for_timeout(80)
        check('Two-finger touch zoom changes chart span',page.evaluate('__nautilus.chart.span')<2700)
        session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
        check('Touch release clears gesture state',page.evaluate('__nautilus.chart.touches.size===0 && __nautilus.chart.pinch===null'))
        session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':points(70)[:1]})
        session.send('Input.dispatchTouchEvent',{'type':'touchCancel','touchPoints':[]})
        check('Touch cancellation clears drag safely',page.evaluate('__nautilus.chart.drag===null'))
        for w,h in [(320,568),(430,932),(844,390)]:
            page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(100)
            check(f'Compact viewport {w}x{h} has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
            if h>=680:
                check(f'Compact viewport {w}x{h} fits vertically',fits())
                check(f'Hero values and branding fit at {w}px',page.evaluate("['targetValue','btcValue','timerValue'].every(id=>{let e=document.getElementById(id);return e.scrollWidth<=e.clientWidth+1}) && document.querySelector('.brand h1').scrollWidth<=document.querySelector('.brand h1').clientWidth+1"))
            else:check('Very short landscape viewport allows scrolling, not clipping',page.evaluate("document.documentElement.scrollHeight>innerHeight && getComputedStyle(document.body).overflowY==='auto'"))
        check('No browser exceptions during layout/interaction acceptance',not errors)
        # Coarse-pointer rules use a real emulated touch context, not just pointer IDs.
        context.close()
        context=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,device_scale_factor=1)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        mount()
        check('Touch context fits phone viewport',fits())
        check('Touch controls have at least 44px height',page.evaluate("['displaySettings','bridgeFullscreen','zoomIn','zoomOut','fullChart'].every(id=>document.getElementById(id).getBoundingClientRect().height>=44)"))
        context.close()
        context=browser.new_context(viewport={'width':1664,'height':806})
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        mount({'nautilus.display.v1.1':saved})
        check('Saved text size is restored on a fresh page',page.evaluate('__nautilus.display.getPreference().scale===1.3'))
        page.click('#displaySettings');page.select_option('#layoutMode','mobile');page.click('#closeDisplay')
        check('Explicit phone preview is available on desktop',page.get_attribute('body','data-layout')=='mobile')
        page.click('#displaySettings');page.click('#resetDisplay');page.click('#closeDisplay')
        check('Reset returns to auto Bridge',page.get_attribute('body','data-layout')=='bridge')
        check('Final browser exception count is zero',not errors)
        browser.close()
    (output/'bridge_validation.json').write_text(json.dumps({'checks_passed':len(checks),'checks':checks,'browser_errors':errors,'snapshot_source':Path(sys.argv[1]).name},indent=2))

if __name__=='__main__':main()
