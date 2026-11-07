
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
