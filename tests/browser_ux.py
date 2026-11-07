"""Real Chromium journeys on shipped UI with explicitly synthetic API fixtures.

Run separately: python tests/browser_ux.py --out <evidence-directory>.
Requires Playwright + Chromium. No live IRIS or model claim.
Browser ownership: local_browser: true (multi-page, keyboard, history and session checks).
"""
import argparse
import base64
import functools
import hashlib
import json
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT/'tests/fixtures/ux_cases.json').read_text())
FIXTURE = '''
// seam: API network boundary. Real UI code; synthetic operations only.
const fixtureCases = CASES;
const oldFetch = window.fetch;
window.uxTest = {signedIn:true, posts:[], failExplain:false, stale:false, version:1};
window.fetch = async (input, options={}) => {
 const path=String(input), cfg=window.uxTest;
 const response=(data,status=200)=>Promise.resolve(new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}}));
 if(path==='/api/session') { cfg.signedIn=true; sessionStorage.setItem('ux-auth','yes');return response({ok:true}); }
 if(path==='/api/session/logout') { cfg.signedIn=false;return response({ok:true}); }
 if(new URL(location.href).searchParams.has('login') && sessionStorage.getItem('ux-auth')!=='yes') cfg.signedIn=false;
 if(!cfg.signedIn) return response({detail:'Operator sign-in required.'},401);
 if(path==='/api/cases') return response({available:true,items:new URL(location.href).searchParams.has('no-cases')?[]:Object.values(fixtureCases),budget:{operator_daily_used:1,operator_daily_limit:20,operator_active_limit:2}});
 if(path.endsWith('/full-review')) { cfg.posts.push({path,body:JSON.parse(options.body)}); return response({status:'ready',content:{what_happened:'The saved receipt says the original request succeeded; a later read shows different settings.',where_judgment_changed:'The historical review remains recorded, while the current settings need separate interpretation.',human_path:'No human decision is recorded.',unresolved:'The author and purpose of the later change are unknown.',human_choice_assessment:'NO_DECISION',human_reason_assessment:'NO_DECISION',evidence_ids:['receipt','review','configuration']}}); }
 if(path.endsWith('/explain')) { cfg.posts.push({path,body:JSON.parse(options.body)}); return response({status:'unavailable',detail:'Model unavailable. Your evidence summary remains usable.'}); }
 if(path.endsWith('/decision')) {
  cfg.posts.push({path,body:JSON.parse(options.body)});
  if(cfg.stale) { fixtureCases.changed.brief.revision='changed-revision'; return response({detail:'Evidence changed. Review current facts.'},409); }
  await new Promise(resolve=>setTimeout(resolve,200));
  return response({next_step:'Your intention was recorded. No configuration was changed.'});
 }
 if(path.startsWith('/api/cases/')) { const id=decodeURIComponent(path.split('/').pop());const c=Object.values(fixtureCases).find(c=>c.id===id);return response(c||{detail:'Case not found'},c?200:404); }
 if(path.startsWith('/api/receipts/') && cfg.receiptFailure) return response({detail:'Receipt service unavailable'},503);
 if(path.startsWith('/api/receipts/') && cfg.wrongReceipt) return response({receipt:{id:'different-receipt',target:'task:99',status:'VERIFIED_SUCCESS'}});
 if(path.startsWith('/api/receipts/') && !path.endsWith('/reconcile')) return response({receipt:{id:path.split('/').pop(),status:cfg.receiptStatus||'VERIFIED_SUCCESS',target:'task:17',operator:'owner',action_id:'task.run-once',before_evidence:[],after_evidence:[],explanation:'Synthetic task history established the result.'},evidence:[{source:'synthetic history',id:'fixture-evidence',captured_at:'2026-11-05',value:{result:'success'}}],ledger:[]});
 return oldFetch(input,options);
};
'''.replace('CASES',json.dumps(CASES))

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path.split('?')[0] == '/':
            html=(ROOT/'static/index.html').read_text()
            scripts='<script>'+(ROOT/'tests/fixtures/demo-api.js').read_text()+'\n'+FIXTURE+'</script>'
            html=re.sub(r'(<script src="/static/app\.js(?:\?[^\"]*)?"></script>)',lambda match:scripts+match.group(1),html)
            raw=html.encode();self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        else: super().do_GET()

def run(out):
    out.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_address[1]}'
    checks=[];views=[];errors=[]
    def check(name,condition):
        checks.append({'name':name,'passed':bool(condition)})
        if not condition: raise AssertionError(name)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            for width in [320,360,390,768,1440,2560,3440]:
                context=browser.new_context(viewport={'width':width,'height':900},reduced_motion='reduce')
                context.add_init_script("localStorage.setItem('battery-guide-seen-v2','1')")
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin);page.locator('.case-receipt').wait_for()
                check(f'{width}: cases first',page.locator('#page-title').inner_text()=='Cases')
                check(f'{width}: logo loaded',page.locator('.brand img').evaluate('(e)=>e.complete && e.naturalWidth>0'))
                check(f'{width}: latest review opens directly',page.url.endswith('#cases/'+CASES['complete']['id']))
                check(f'{width}: linked receipt visible',page.locator('.case-receipt').get_by_text('The requested result was verified.',exact=True).is_visible())
                check(f'{width}: what happened visible',page.get_by_role('heading',name='What happened',exact=True).is_visible())
                check(f'{width}: receipt details closed',not page.get_by_text('Receipt details',exact=True).evaluate('(e)=>e.parentElement.open'))
                positions=page.evaluate('''()=>{const a=document.querySelector('.case-receipt').getBoundingClientRect(),b=document.querySelector('.review-story').getBoundingClientRect();return {left:a.x,right:b.x,top:a.y,next:b.y,bottom:a.bottom}}''')
                check(f'{width}: receipt and story reading order',positions['next']>=positions['bottom'] or (positions['right']>positions['left'] and abs(positions['next']-positions['top'])<2))
                page.get_by_role('button',name='Back to cases',exact=True).click()
                page.locator('[data-case-id="case-context"]').click();page.locator('#decision-reason').wait_for()
                order=page.evaluate('''() => [...document.querySelectorAll('.case-overview,.receipt-review,.brief-context,.full-case-review,.decision-brief')].map(e=>['case-overview','receipt-review','brief-context','full-case-review','decision-brief'].find(name=>e.classList.contains(name)))''')
                check(f'{width}: answer and decision precede detailed evidence',order==['case-overview','decision-brief','receipt-review','brief-context','full-case-review'])
                if width >= 2560:
                    canvas=page.evaluate('''()=>{const rect=s=>document.querySelector(s).getBoundingClientRect();const main=rect('main'),overview=rect('.case-overview'),question=rect('.case-overview h2'),logic=rect('.case-logic');return {mainLeft:main.left,mainRight:main.right,mainWidth:main.width,used:overview.width/main.width,logicBeside:logic.left>question.right}}''')
                    check(f'{width}: case uses a balanced working canvas',abs(canvas['mainLeft']-(width-canvas['mainRight']))<3 and canvas['mainWidth']>=1900 and canvas['used']>.85)
                    check(f'{width}: question and explanation share the top row',canvas['logicBeside'])
                    check(f'{width}: focused case stage is centered',page.evaluate('''()=>{const r=document.querySelector('.case-slide .case-action').getBoundingClientRect(),m=document.querySelector('main').getBoundingClientRect();return Math.abs((r.left+r.right)/2-(m.left+m.right)/2)<3}'''))
                check(f'{width}: receipt uses a distinct paper surface',page.locator('.case-receipt').evaluate('(e)=>getComputedStyle(e).backgroundColor!==getComputedStyle(document.querySelector(".review-story")).backgroundColor && getComputedStyle(e).getPropertyValue("--paper").trim()==="#f2eadb"'))
                page.wait_for_function("document.querySelector('.case-stage-label')?.textContent.startsWith('1 of 3')")
                check(f'{width}: full review is opt in',page.evaluate('uxTest.posts.filter(p=>p.path.endsWith("/full-review")).length')==0)
                page.get_by_role('button',name='Review full case with AI Hub',exact=True).click()
                page.locator('.full-case-review').get_by_text('The author and purpose of the later change are unknown.',exact=True).wait_for()
                check(f'{width}: bounded review uses one explicit request',page.evaluate('uxTest.posts.filter(p=>p.path.endsWith("/full-review")).length')==1)
                page.locator('.full-case-review').get_by_role('button',name='Saved operation receipt',exact=True).click()
                check(f'{width}: full review citation opens receipt',page.locator('#receipt-source').evaluate('(e)=>e.open'))
                page.get_by_text('Receipt details',exact=True).click()
                check(f'{width}: original operation and current settings distinguished','saved receipt verifies' in page.locator('.case-logic').inner_text() and 'later read shows different settings' in page.locator('.case-logic').inner_text())
                check(f'{width}: choices not preselected',page.locator('input[name=decision-choice]:checked').count()==0)
                check(f'{width}: technical initially closed',not page.get_by_text('Technical details and full evidence',exact=True).evaluate('(e)=>e.parentElement.open'))
                check(f'{width}: scope visible','Simulated operation' in page.locator('.decision-brief').inner_text())
                page.evaluate("setCaseStage(document.querySelector('.case-carousel'),0)")
                page.wait_for_function("document.querySelector('.case-stage-label')?.textContent.startsWith('1 of 3')")
                check(f'{width}: current task is first stage',page.locator('.case-stage-label').inner_text().startswith('1 of 3'))
                page.get_by_role('button',name='Next case stage').click()
                check(f'{width}: arrow opens report',page.locator('.case-stage-label').inner_text().startswith('2 of 3'))
                page.get_by_role('button',name='Next case stage').click()
                check(f'{width}: arrow opens sources',page.locator('.case-stage-label').inner_text().startswith('3 of 3'))
                page.get_by_role('button',name='Previous case stage').click()
                check(f'{width}: arrow returns to report',page.locator('.case-stage-label').inner_text().startswith('2 of 3'))
                page.locator('.case-track').evaluate('(e)=>{e.scrollLeft=0}')
                page.wait_for_timeout(180)
                check(f'{width}: horizontal scroll returns to task',page.locator('.case-stage-label').inner_text().startswith('1 of 3'))
                m=page.evaluate('''() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:[...document.querySelectorAll('button,input,select,textarea')].filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,type:e.type,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height})),fonts:[...document.querySelectorAll('.decision-brief > p')].map(e=>getComputedStyle(e).fontSize)})''')
                views.append(m);check(f'{width}: no horizontal overflow',m['scrollWidth']<=width)
                if width>=2000:
                    check(f'{width}: working canvas stays centered',page.locator('main').evaluate('(e)=>{const r=e.getBoundingClientRect();return Math.abs(r.left-(innerWidth-r.right))<3}'))
                check(f'{width}: 44px working controls',all(c['h']>=44 for c in m['controls'] if c['type'] not in ['radio','checkbox']))
                contrast=page.evaluate("""() => {
                  const vars=getComputedStyle(document.documentElement);
                  const lum=color=>{const a=color.trim().match(/[a-f0-9]{2}/gi).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return .2126*a[0]+.7152*a[1]+.0722*a[2]};
                  const ratio=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
                  const bar=getComputedStyle(document.querySelector('.status-bar'));
                  return {text:ratio(vars.getPropertyValue('--text'),vars.getPropertyValue('--surface')),secondary:ratio(vars.getPropertyValue('--text-2'),vars.getPropertyValue('--surface')),input:ratio(vars.getPropertyValue('--control-border'),vars.getPropertyValue('--surface')),focus:ratio(vars.getPropertyValue('--focus'),vars.getPropertyValue('--surface')),headerSafe:ratio(bar.getPropertyValue('--safe'),bar.getPropertyValue('--surface'))};
                }""")
                m['contrast']=contrast
                check(f'{width}: palette contrast',contrast['text']>=4.5 and contrast['secondary']>=4.5 and contrast['input']>=3 and contrast['focus']>=3 and contrast['headerSafe']>=4.5)
                check(f'{width}: every story assertion has a named source',page.locator('.case-story > li .source-link').count()==3)
                check(f'{width}: readable source type and timestamp','Review updated' in page.locator('.case-story .source-note').first.inner_text())
                page.locator('.case-receipt').get_by_role('button',name='Saved operation receipt',exact=True).click()
                check(f'{width}: receipt citation opens exact record',page.locator('#receipt-source').evaluate('(e)=>e.open && e.querySelector("summary")===document.activeElement') and CASES['changed']['receipt_id'] in page.locator('#receipt-source').inner_text())
                page.get_by_text('Receipt details',exact=True).click()
                page.get_by_role('button',name='Recorded review result',exact=True).focus()
                page.get_by_role('button',name='Recorded review result',exact=True).press('Enter')
                check(f'{width}: keyboard citation opens the conclusion',page.locator('#story-source-2').evaluate('(e)=>e.open && e.querySelector("summary")===document.activeElement') and 'case-context' in page.locator('#story-source-2').inner_text())
                page.get_by_text('Review conclusion details',exact=True).click()
                page.locator('.brief-sources').get_by_role('button',name='Current configuration comparison',exact=True).click()
                check(f'{width}: nested citation reveals source and focus',page.locator('#decision-fact-configuration').is_visible() and page.locator('#decision-fact-configuration').evaluate('(e)=>document.activeElement===e'))
                check(f'{width}: comparison citation retains observation time','2026-11-05 22:04:42 UTC' in page.locator('.brief-sources').inner_text())
                page.get_by_text('Why is Battery showing this?',exact=True).click()
                page.get_by_text('More explanation',exact=True).click()
                page.screenshot(path=str(out/f'decision-{width}.png'),full_page=True)
                # Enter context; keep it through receipt navigation and browser history.
                page.locator('#decision-reason').fill('The later configuration is intentional.')
                page.locator('input[value=keep_current]').check()
                page.get_by_text('Review conclusion details',exact=True).click()
                page.get_by_text('Technical details and full evidence',exact=True).click()
                page.get_by_role('button',name='Inspect operation receipt',exact=True).first.click()
                page.locator('.receipt-document').wait_for()
                check(f'{width}: receipt route',page.url.split('#')[-1].startswith('receipts/'))
                page.get_by_role('button',name='Back to case',exact=True).click();page.locator('#decision-reason').wait_for()
                check(f'{width}: draft retained',page.locator('#decision-reason').input_value()=='The later configuration is intentional.')
                check(f'{width}: choice retained',page.locator('input[value=keep_current]').is_checked())
                check(f'{width}: history disclosure retained',page.get_by_text('Review conclusion details',exact=True).evaluate('(e)=>e.parentElement.open'))
                check(f'{width}: technical disclosure retained',page.get_by_text('Technical details and full evidence',exact=True).evaluate('(e)=>e.parentElement.open'))
                check(f'{width}: no carried receipt success',not page.locator('#status-message').inner_text())
                # Browser history follows the same case/receipt routes.
                page.go_back();page.locator('.receipt-document').wait_for()
                page.go_forward();page.locator('#decision-reason').wait_for()
                check(f'{width}: browser history restores case',page.url.endswith('#cases/case-context'))
                # Keyboard expands history without moving away from the case.
                history=page.get_by_text('Review conclusion details',exact=True)
                history.focus();history.press('Enter')
                check(f'{width}: keyboard disclosure works',not history.evaluate('(e)=>e.parentElement.open'))
                history.press('Enter')
                # Refresh preserves text selection and reading position.
                page.locator('#decision-reason').focus();page.locator('#decision-reason').evaluate('(e)=>e.setSelectionRange(4,12)')
                before=page.evaluate('scrollY')
                page.evaluate('document.querySelector("#decision-reason").setSelectionRange(4,12); loadNativeCases(state.caseId)')
                check(f'{width}: focused draft survives refresh',page.locator('#decision-reason').evaluate('(e)=>document.activeElement===e && e.selectionStart===4 && e.selectionEnd===12'))
                check(f'{width}: scroll survives refresh',abs(page.evaluate('scrollY')-before)<3)
                page.get_by_role('button',name='Record decision',exact=True).dblclick()
                page.wait_for_timeout(350)
                check(f'{width}: one decision request',page.evaluate('uxTest.posts.filter(p=>p.path.endsWith("/decision")).length')==1)
                # Search has stable focus and can be typed normally.
                page.get_by_role('button',name='Back to cases',exact=True).click();page.locator('#case-search').fill('no such target')
                check(f'{width}: search empty state','No cases match' in page.locator('#page-content').inner_text())
                page.locator('#case-search').fill('');page.locator('[data-case-id]').first.click()
                page.locator('.decision-brief').wait_for()
                check(f'{width}: completed review has no choices',page.locator('input[name=decision-choice]').count()==0)
                page.get_by_text('More explanation',exact=True).click()
                page.get_by_role('button',name='Explain this evidence',exact=True).click()
                page.get_by_text('Model unavailable. Your evidence summary remains usable.',exact=True).wait_for()
                check(f'{width}: explanation failure retains summary',page.locator('.decision-brief > h2').is_visible())
                page.screenshot(path=str(out/f'complete-{width}.png'),full_page=True)
                if width==360:
                    page.evaluate('document.documentElement.style.fontSize="200%"')
                    check('200% text: no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    page.screenshot(path=str(out/'complete-text200.png'),full_page=True)
                context.close()
            # Explicit protected destination survives login reload.
            context=browser.new_context(viewport={'width':390,'height':844});context.add_init_script("localStorage.setItem('battery-guide-seen-v2','1')");page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin+'/?login#cases/case-context');page.locator('#login-panel').wait_for(state='visible')
            if page.locator('#help-dialog').evaluate('(e)=>e.open'): page.get_by_role('button',name='Skip practice').click()
            page.locator('#access-key').fill('fixture-key');page.get_by_role('button',name='Sign in',exact=True).click()
            page.locator('#decision-reason').wait_for();check('login returns to requested case',page.url.endswith('#cases/case-context'))
            # Stale submission preserves draft and refreshes the actual evidence revision.
            page.locator('#decision-reason').fill('Preserve this draft when the evidence changes.');page.locator('input[value=defer]').check()
            page.evaluate('uxTest.stale=true');page.get_by_role('button',name='Record decision',exact=True).click()
            page.wait_for_timeout(250)
            check('stale decision retains draft',page.locator('#decision-reason').input_value().startswith('Preserve this draft'))
            check('stale decision prompts comparison','Evidence changed' in page.locator('#status-message').inner_text())
            # Expiry removes drafts and all case data; late calls cannot repaint it.
            page.evaluate('uxTest.signedIn=false; loadNativeCases(state.caseId)')
            check('expiry removes case data',page.locator('#page-content').inner_text()=='')
            check('expiry clears draft memory',page.evaluate('Object.keys(state.decisionDrafts).length')==0)
            context.close()
            # Every visitor can finish a safe, interactive first-run practice case.
            for width in [320,390,1440]:
                context=browser.new_context(viewport={'width':width,'height':844});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin);page.locator('#help-dialog').wait_for(state='visible')
                if width==390: page.screenshot(path=str(out/'first-run-guide-390.png'))
                check(f'{width}: first visit offers practice',page.locator('#help-progress').inner_text()=='Practice case · step 1 of 5')
                check(f'{width}: next waits for participation',page.locator('#help-next').is_disabled())
                check(f'{width}: practice choices visible',page.get_by_role('button',name='Check the original attempt').is_visible())
                check(f'{width}: guide controls fit viewport',page.locator('#help-next').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.top>=0 && r.bottom<=innerHeight && r.width>=44}') )
                page.get_by_role('button',name='Send the task again').click()
                check(f'{width}: unsafe choice explains duplicate risk','could run the task twice' in page.locator('#help-feedback').inner_text())
                page.get_by_role('button',name='Check the original attempt').click()
                page.get_by_role('button',name='Next',exact=True).click()
                check(f'{width}: receipt initially concealed',page.locator('.help-record').is_hidden())
                page.get_by_role('button',name='Inspect practice receipt').click()
                check(f'{width}: saved receipt revealed','One dispatch recorded' in page.locator('.help-record').inner_text())
                page.get_by_role('button',name='Next',exact=True).click()
                page.get_by_role('button',name='Compare practice history').click()
                check(f'{width}: fresh observation revealed','One new Success row' in page.locator('.help-record').inner_text())
                page.get_by_role('button',name='Next',exact=True).click()
                page.get_by_role('button',name='The first confident answer').click()
                check(f'{width}: first agent error corrected','Confidence is not evidence' in page.locator('#help-feedback').inner_text())
                page.get_by_role('button',name='The evidence-backed later review').click()
                page.get_by_role('button',name='Next',exact=True).click()
                page.get_by_role('button',name='Keep the receipt; do not rerun').click()
                check(f'{width}: full practice stays read only',page.evaluate('uxTest.posts.length')==0)
                page.get_by_role('button',name='Enter Battery').click()
                check(f'{width}: completion remembered',page.evaluate("localStorage.getItem('battery-guide-seen-v2')")=='1')
                check(f'{width}: practice closes',not page.locator('#help-dialog').evaluate('(e)=>e.open'))
                page.locator('.case-overview.app-tour-target').wait_for(state='visible')
                check(f'{width}: working tour opens real case',page.locator('.case-overview.app-tour-target').count()==1)
                if width in [390,1440]: page.screenshot(path=str(out/f'app-tour-case-{width}.png'))
                page.get_by_role('button',name='Next',exact=True).click()
                page.locator('.case-logic-sources.app-tour-target').wait_for(state='visible')
                check(f'{width}: working tour points to source links',page.locator('.case-logic-sources.app-tour-target').count()==1)
                page.get_by_role('button',name='Next',exact=True).click()
                page.locator('.review-story.app-tour-target').wait_for(state='visible')
                check(f'{width}: working tour opens report stage',page.locator('.case-stage-label').inner_text().startswith('2 of 3') and page.locator('.review-story.app-tour-target').count()==1)
                page.get_by_role('button',name='Next',exact=True).click()
                page.locator('#lifecycle.app-tour-target').wait_for(state='visible')
                check(f'{width}: working tour opens request procedure',page.locator('#lifecycle.app-tour-target').count()==1 and page.url.endswith('#request'))
                if width==390: page.screenshot(path=str(out/'app-tour-request-390.png'))
                check(f'{width}: working tour never posts',page.evaluate('uxTest.posts.length')==0)
                page.get_by_role('button',name='Finish tour').click()
                check(f'{width}: working tour clears highlight',page.locator('.app-tour-target').count()==0 and page.locator('#app-tour').is_hidden())
                page.get_by_role('button',name='Open practice walkthrough').click()
                check(f'{width}: corner help replays practice',page.locator('#help-progress').inner_text()=='Practice case · step 1 of 5')
                if width==320:
                    page.evaluate('document.documentElement.style.fontSize="200%"')
                    check('practice at 200% text has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    page.locator('#help-next').scroll_into_view_if_needed()
                    check('practice controls reachable at 200% text',page.locator('#help-next').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.top>=0 && r.bottom<=innerHeight}'))
                page.get_by_role('button',name='Skip practice').click();context.close()
            # A protected installation offers the same practice before sign-in.
            context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page()
            page.goto(origin+'/?login#cases/case-context');page.locator('#login-panel').wait_for(state='visible');page.locator('#help-dialog').wait_for(state='visible')
            check('signed-out visitor can practice',page.get_by_role('button',name='Check the original attempt').is_visible())
            page.get_by_role('button',name='Skip practice').click();context.close()
            context=browser.new_context(viewport={'width':390,'height':844})
            page=context.new_page();page.goto(origin);page.evaluate("localStorage.setItem('battery-guide-seen-v2','1');sessionStorage.setItem('battery-tour-pending','1')")
            page.goto(origin+'/?login#cases/case-context');page.locator('#login-panel').wait_for(state='visible')
            check('working tour waits for sign-in',page.locator('#app-tour').is_hidden())
            page.locator('#access-key').fill('fixture-key');page.get_by_role('button',name='Sign in',exact=True).click()
            page.locator('.case-overview.app-tour-target').wait_for(state='visible')
            check('working tour resumes after sign-in',page.locator('#app-tour').is_visible())
            page.get_by_role('button',name='End tour').click();context.close()
            context=browser.new_context(viewport={'width':390,'height':844})
            page=context.new_page();page.goto(origin);page.evaluate("localStorage.setItem('battery-guide-seen-v2','1');sessionStorage.setItem('battery-tour-pending','1')")
            page.goto(origin+'/?no-cases#overview');page.locator('.proof-result.app-tour-target').wait_for(state='visible')
            check('no-case tour starts at Overview',page.locator('#app-tour-title').inner_text()=='Begin at Overview')
            page.get_by_role('button',name='Next',exact=True).click();page.locator('#lifecycle.app-tour-target').wait_for(state='visible')
            check('no-case tour still reaches request procedure',page.url.endswith('#request'))
            page.get_by_role('button',name='Finish tour').click();context.close()
            # Repeated switching across the actual app screens, including unavailable coverage.
            context=browser.new_context(viewport={'width':390,'height':844});context.add_init_script("localStorage.setItem('battery-guide-seen-v2','1')");page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin);page.locator('.case-receipt').wait_for()
            import random
            names=['overview','tasks','webapps','rest','permissions','security','os','logs','receipts','ledger','rules','cases']
            random.Random(49).shuffle(names)
            for name in names:
                page.locator('.nav-toggle').click()
                if name in {'tasks','webapps','receipts','rest','permissions','security','os','logs','ledger','rules'}:
                    page.locator('.nav-more summary').click()
                page.locator(f'[data-page={name}]').click()
                check(f'navigation: {name}',(page.url.endswith('#'+name) or name=='cases' and '#cases/' in page.url) and page.locator('#page-title').inner_text())
                check(f'navigation reflow: {name}',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            page.goto(origin+'/#cases/case-context');page.locator('#decision-reason').wait_for()
            page.evaluate('fixtureCases.changed.brief.differences[0].current="X".repeat(300); fixtureCases.changed.brief.summary="<img src=x onerror=alert(1)>";loadNativeCases(state.caseId)')
            check('hostile evidence is rendered as text',page.locator('.case-overview img').count()==0 and '<img' in page.locator('.case-overview').inner_text())
            check('long values reflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            page.evaluate('fixtureCases.changed.explanation={status:"ready",content:{summary:"The saved result passed.",meaning:"Current intent still needs your input.",missing:"The reason for the later change is unknown.",evidence_ids:["review","configuration"]}};loadNativeCases(state.caseId)')
            page.get_by_text('More explanation',exact=True).click()
            page.get_by_role('heading',name='AI explanation — interpretation of the evidence',exact=True).wait_for()
            ai=page.get_by_role('heading',name='AI explanation — interpretation of the evidence',exact=True).locator('..')
            check('AI sources use labels rather than raw identifiers',ai.get_by_role('button',name='Current configuration comparison',exact=True).is_visible() and ai.get_by_role('button',name='Recorded review',exact=True).is_visible())
            check('AI attribution accurately covers the whole explanation','Sources cited for this explanation as a whole:' in ai.inner_text())
            ai.get_by_role('button',name='Recorded review',exact=True).click()
            check('AI source reveals matching fact',page.locator('#decision-fact-review').is_visible() and 'VERIFIED_MATCH' in page.locator('#decision-fact-review').inner_text())
            check('citations leave operation and model calls untouched',page.evaluate('uxTest.posts.length')==0)
            page.evaluate('uxTest.receiptFailure=true; loadNativeCases(state.caseId)')
            page.get_by_text('The receipt could not be displayed.',exact=True).wait_for()
            check('receipt failure keeps review and exposes gap',page.locator('.decision-brief').is_visible() and 'Receipt service unavailable' in page.locator('.case-receipt').inner_text())
            check('failed receipt never presents saved success', 'The requested result was verified.' not in page.locator('.case-receipt').inner_text())
            page.evaluate('uxTest.receiptFailure=false;uxTest.wrongReceipt=true;loadNativeCases(state.caseId)')
            page.get_by_text('The returned receipt does not match this review.',exact=True).wait_for()
            check('wrong receipt rejected', 'The requested result was verified.' not in page.locator('.case-receipt').inner_text())
            page.evaluate('uxTest.wrongReceipt=false;uxTest.receiptStatus="OUTCOME_UNKNOWN";loadNativeCases(state.caseId)')
            page.get_by_text('We do not yet know whether the operation completed.',exact=True).wait_for()
            check('operation uncertainty distinct from review match',page.locator('.review-story').get_by_text('Evidence matched the request.',exact=True).is_visible())
            check('unknown receipt has its own visible treatment',page.locator('.receipt-verdict[data-outcome="OUTCOME_UNKNOWN"]').count()==1)
            check('reading does not submit reviews or operations',page.evaluate('uxTest.posts.length')==0)
            page.goto(origin+'/#cases/all');page.locator('#case-search').wait_for()
            check('explicit case list survives reload',page.url.endswith('#cases/all'))
            page.reload();page.locator('#case-search').wait_for()
            check('case list stays browsable',page.url.endswith('#cases/all'))
            page.goto(origin+'/#cases/missing');page.get_by_text('This case could not be opened. Return to cases or refresh.',exact=True).wait_for()
            check('missing route never substitutes another case',page.locator('.case-receipt').count()==0)
            page.get_by_role('button',name='Back to cases',exact=True).click();page.locator('#case-search').wait_for()
            check('missing case can return to list',page.url.endswith('#cases/all'))
            context.close();browser.close()
        check('no browser exceptions',not errors)
    finally:
        server.shutdown();server.server_close()
        report={'fixture_scope':'Real Chromium UI with synthetic API network fixtures. No live IRIS or inference.', 'checks':checks,'views':views,'browser_errors':errors,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['static/index.html','static/app.js','static/app.css','static/battery-logo.png','tests/fixtures/ux_cases.json','tests/fixtures/demo-api.js']}}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'passed':sum(c['passed'] for c in checks),'checks':len(checks),'errors':errors,'report':str(out/'report.json')}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);run(parser.parse_args().out)
