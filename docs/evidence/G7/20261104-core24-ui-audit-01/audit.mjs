// Actual installed UI observations. No source/CSS overlays or business writes.
import path from 'node:path';import {browserRuntime} from './browser_runtime.mjs';
const mode=process.argv[2];if(!['baseline','zoom200'].includes(mode))throw Error('Select audit mode');
const b=await browserRuntime(path.join(process.cwd(),'.local/g7-core24-ui-audit-01',mode));
const {input,before}=b,A=input.fixture.workspaces.A,note=before.mp_example_note.find(n=>n.workspace_id===A.id),foreign=before.mp_example_note.find(n=>n.workspace_id!==A.id);
const settings=input.base+'/app/settings?workspace='+A.public_id,notes=input.base+'/app/org.example.notes/?workspace='+A.public_id,form=notes+'&note='+note.public_id;
const observations=[],findings=[];
const readySettings=`!!document.querySelector('#mp_workspace_name')&&!document.querySelector('.mp_notice[role="status"]')&&!document.querySelector('.mp_notice[role="alert"]')`;
async function nav(url,ready){await b.navigate(url);await b.until(()=>b.evaluate(ready),'complete UI loading');}
const metrics=()=>b.evaluate(`({inner_width:innerWidth,inner_height:innerHeight,outer_width:outerWidth,outer_height:outerHeight,dpr:devicePixelRatio,visual_scale:visualViewport.scale,root_width:document.documentElement.clientWidth,scroll_width:document.documentElement.scrollWidth,header_width:document.querySelector('.mp_header')?.scrollWidth,header_client_width:document.querySelector('.mp_header')?.clientWidth,lang:document.documentElement.lang,dir:document.documentElement.dir})`);
const colors=selector=>b.evaluate(`(()=>{const parse=s=>s.match(/[\\d.]+/g)?.map(Number)||[0,0,0,0],mix=(a,b)=>a.slice(0,3).map((v,i)=>v*(a[3]??1)+b[i]*(1-(a[3]??1)));const bg=e=>{if(!e)return [255,255,255];return mix(parse(getComputedStyle(e).backgroundColor),bg(e.parentElement));};const lum=c=>c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);return [...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).map(e=>{const s=getComputedStyle(e),background=bg(e),foreground=mix(parse(s.color),background),l=[lum(foreground),lum(background)],ratio=(Math.max(...l)+.05)/(Math.min(...l)+.05),large=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&parseInt(s.fontWeight)>=700);return {tag:e.tagName,text:e.matches('input,textarea')?'(field)':e.textContent.trim().slice(0,120),class:e.className,color:s.color,background:s.backgroundColor,effective_background:background,ratio:Number(ratio.toFixed(3)),required:large?3:4.5,disabled:!!e.disabled,font_size:s.fontSize,font_weight:s.fontWeight,outline:s.outlineStyle,outline_width:s.outlineWidth,outline_color:s.outlineColor,filter:s.filter,background_image:s.backgroundImage==='none'?'none':'present',focused:e===document.activeElement,focus_visible:e.matches(':focus-visible')};});})()`);
const active=()=>b.evaluate(`({tag:document.activeElement.tagName,name:document.activeElement.tagName==='BODY'?'(document)':(document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()).slice(0,100),inside_modal:!!document.activeElement.closest('.modal'),inside_labels:!!document.activeElement.closest('.mp_label_dialog')})`);
async function tabTo(name){for(let i=0;i<45;i++){if((await active()).name===name)return;await b.key('Tab','Tab',9);}throw Error('Keyboard target absent: '+name);}
async function sample(name,selector){const data=await colors(selector);observations.push({name,data});for(const x of data)if(!x.disabled&&x.ratio+0.001<x.required)findings.push({check:name,text:x.text,ratio:x.ratio,required:x.required});return data;}
try{
 await nav(settings,readySettings);
 await b.select('#mp_shell_language','en-US');await b.until(()=>b.evaluate(readySettings+`&&document.documentElement.lang==='en-US'`),'English settings loaded');
 observations.push({name:'actual_window_zoom_metrics',data:await metrics()});
 for(const theme of ['light','dark']){
  await b.select('#mp_shell_theme',theme);await b.until(()=>b.evaluate(`document.body.dataset.theme===${JSON.stringify(theme)}`),'theme');
  await sample(theme+'-settings-all-headings-and-controls','.mp_root h1,.mp_root h2,.mp_root h3,.mp_root h4,.mp_root h5,.mp_root h6,.mp_root label,.mp_root button,.mp_root select,.mp_subtitle');
  await b.screenshot(theme+'-settings.png');
  await nav(form,`!!document.querySelector('.o_form_view .o_field_widget[name="title"]')&&!document.querySelector('.mp_notice[role="alert"]')`);
  await b.evaluate(`document.querySelector('.o_field_widget[name="title"] input').focus()`);await b.key('Tab','Tab',9);
  await sample(theme+'-native-fields','.o_field_widget input,.o_field_widget textarea');
  const main=await b.ax('.mp_main main.o_content'),title=await b.ax('.o_field_widget[name="title"] input');
  await tabTo('Delete note');const initiator=await active();await b.key('Enter','Enter',13);await b.until(()=>b.evaluate(`!!document.querySelector('.modal .modal-content')`),'native confirmation');
  const modalAX=await b.ax('.modal'),cycle=[];for(let i=0;i<6;i++){cycle.push(await active());await b.key('Tab','Tab',9);}
  const modalColors=await sample(theme+'-native-modal','.modal-title,.modal-content .btn,.modal .btn-close');await b.screenshot(theme+'-confirm.png');
  await b.key('Escape','Escape',27);await b.until(()=>b.evaluate(`!document.querySelector('.modal .modal-content')`),'native Escape');
  observations.push({name:theme+'-native-modal-keyboard',data:{main,title,initiator,modalAX,cycle,restored:await active(),confirmed:false}});
  await tabTo('Edit labels');await b.key('Enter','Enter',13);await b.until(()=>b.evaluate(`!!document.querySelector('.mp_label_dialog[open]')`),'Labels');
  const labelAX=await b.ax('.mp_label_dialog'),fieldAX=await b.ax('.mp_label_dialog textarea');await sample(theme+'-Labels','.mp_label_dialog h2,.mp_label_dialog textarea,.mp_label_dialog button');
  await b.screenshot(theme+'-labels.png');await b.key('Escape','Escape',27);await b.until(()=>b.evaluate(`!document.querySelector('.mp_label_dialog')`),'Labels Escape');
  observations.push({name:theme+'-Labels-keyboard',data:{labelAX,fieldAX,restored:await active(),submitted:false}});
  await nav(settings,readySettings);
 }
 await b.key('k','KeyK',75,2);await b.until(()=>b.evaluate(`!!document.querySelector('.o_command_palette_search input')`),'native commands');
 observations.push({name:'command-search',data:await b.ax('.o_command_palette_search input')});await b.key('Escape','Escape',27);
 await b.rpc('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
 observations.push({name:'reduced-motion',data:await b.evaluate(`({reduce:matchMedia('(prefers-reduced-motion: reduce)').matches,active_animations:document.querySelector('.mp_root').getAnimations({subtree:true}).length})`)});
 await b.select('#mp_shell_language','ar');await b.until(()=>b.evaluate(readySettings+`&&document.documentElement.lang==='ar'&&document.documentElement.dir==='rtl'`),'Arabic admin loaded');
 observations.push({name:'complete-Arabic-admin',data:await b.evaluate(`({lang:document.documentElement.lang,dir:document.documentElement.dir,headings:[...document.querySelectorAll('.mp_root h1,.mp_root h2,.mp_root h3')].map(e=>e.textContent.trim()),labels:[...document.querySelectorAll('.mp_root label')].map(e=>e.textContent.trim()),theme_name:document.querySelector('#mp_shell_theme').getAttribute('aria-label'),language_name:document.querySelector('#mp_shell_language').getAttribute('aria-label')})`)});
 observations.push({name:'Arabic-window-metrics',data:await metrics()});await b.screenshot('Arabic-settings.png');
 await b.select('#mp_shell_language','en-US');await b.until(()=>b.evaluate(readySettings+`&&document.documentElement.lang==='en-US'`),'English restored');
 await b.select('#mp_shell_theme','light');
 // Native error is readonly; do not submit any dialog, form or Canvas save.
 await nav(notes+'&note='+foreign.public_id,`!!document.querySelector('.mp_notice[role="alert"]')`);
 observations.push({name:'foreign-record-error',data:await b.ax('.mp_notice[role="alert"]')});await b.screenshot('record-denied.png');
 await nav(settings,readySettings);
 await b.save('observations.json',{result:'actual_installed_UI09_audit_not_final_pass',mode,image:input.image_id,generation:5,observations,findings,
   foreign_requests:b.blocked.filter(x=>x.path!=='/mp-ui09-network-probe'),runtime_exceptions:b.exceptions,
   no_business_save_or_delete:true,appearance_restored:true,
   limits:['Real browser window without CDP device metrics override; selected owned-profile zoom preference is recorded separately.',
   'Computed CSS contrast plus screenshots/AX/keyboard observations; no physical screen-reader speech or blanket WCAG compliance claim.',
   'Already measured dark native close glyph residual requires source correction regardless of text-only contrast ratios.']});
 await b.save('network.json',{responses:b.network,blocked:b.blocked,websockets:b.websockets});
 console.log(JSON.stringify({result:'actual_current_UI09_observed',mode,cases:observations.length,contrast_findings:findings.length,foreign:b.blocked.filter(x=>x.path!=='/mp-ui09-network-probe').length,exceptions:b.exceptions.length}));
}catch(error){await b.save('fatal.json',{message:error.message,observations,findings});throw error;}finally{await b.close();}
