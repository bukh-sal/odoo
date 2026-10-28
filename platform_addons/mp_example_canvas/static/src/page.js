/** Plain JS page: public host, DOM, frozen DTOs. No Owl/native env/ORM imports. */
export const CanvasPage={
    async mount({element,host,route,signal}){
        const controller=new AbortController();const abort=()=>controller.abort();signal.addEventListener('abort',abort,{once:true});
        let active=true,dirty=false,board=null,notes=[],attempt=null,currentRoute=route;
        const root=document.createElement('section');root.className='mp_canvas';root.setAttribute('aria-label','Canvas board');element.append(root);
        const header=document.createElement('div');header.className='mp_canvas_header';
        const title=document.createElement('input');title.setAttribute('aria-label','Board name');title.maxLength=100;
        const subtitle=document.createElement('p');subtitle.textContent='Collect ideas. Move them forward.';
        const save=document.createElement('button');save.textContent='Save board';
        const reset=document.createElement('button');reset.textContent='Reload saved board';
        const status=document.createElement('p');status.setAttribute('role','status');status.className='mp_canvas_status';
        header.append(title,subtitle,save,reset,status);
        const form=document.createElement('form');form.className='mp_canvas_add';
        const text=document.createElement('input');text.setAttribute('aria-label','New card text');text.placeholder='An idea, a decision, a next step…';text.maxLength=200;text.required=true;
        const note=document.createElement('select');note.setAttribute('aria-label','Link a note');
        const blank=document.createElement('option');blank.value='';blank.textContent='No linked note';note.append(blank);
        const add=document.createElement('button');add.type='submit';add.textContent='Add card';form.append(text,note,add);
        const lanes=document.createElement('div');lanes.className='mp_canvas_lanes';root.append(header,form,lanes);
        const editable=host.context().capabilities.includes('org.example.canvas:canvas.write');
        title.readOnly=!editable;save.disabled=!editable;form.hidden=!editable;
        const on=(target,event,handler)=>target.addEventListener(event,handler,{signal:controller.signal});
        const changed=()=>{dirty=true;attempt=null;status.textContent='Unsaved changes';};
        const render=()=>{
            lanes.replaceChildren();
            for(const [id,label]of [['inbox','Ideas'],['doing','In progress'],['done','Done']]){
                const lane=document.createElement('section');lane.className='mp_canvas_lane';lane.setAttribute('aria-label',label);
                const heading=document.createElement('h2');heading.textContent=label;lane.append(heading);
                const cards=board.cards.filter(card=>card.lane===id);
                if(!cards.length){const empty=document.createElement('p');empty.className='mp_canvas_empty';empty.textContent='Room for your next idea';lane.append(empty);}
                for(const card of cards){
                    const article=document.createElement('article');article.className='mp_canvas_card';
                    const content=document.createElement('textarea');content.setAttribute('aria-label','Card text');content.value=card.text;content.maxLength=200;content.readOnly=!editable;
                    on(content,'input',()=>{card.text=content.value;changed();});article.append(content);
                    if(card.note_id){const reference=notes.find(value=>value.document_id===card.note_id);const link=document.createElement('button');link.textContent=reference?.content.headline||'Open linked note';on(link,'click',()=>host.navigate({pluginId:'org.example.notes',pageId:'home',query:{note:card.note_id}}));article.append(link);}
                    if(editable){
                        const move=document.createElement('select');move.setAttribute('aria-label','Move card '+card.text);for(const [value,name]of [['inbox','Ideas'],['doing','In progress'],['done','Done']]){const option=document.createElement('option');option.value=value;option.textContent=name;option.selected=value===card.lane;move.append(option);}
                        on(move,'change',()=>{card.lane=move.value;changed();render();});
                        const remove=document.createElement('button');remove.textContent='Remove card';on(remove,'click',()=>{board.cards=board.cards.filter(value=>value.id!==card.id);changed();render();});article.append(move,remove);
                    }
                    lane.append(article);
                }
                lanes.append(lane);
            }
        };
        const load=async next=>{
            const value=await host.services.call('boards','get',next.query.board?{board_id:next.query.board}:{},{signal:controller.signal});
            if(!active||signal.aborted)return;
            board=structuredClone(value);title.value=board.name;dirty=false;attempt=null;status.textContent='Revision '+board.revision+(editable?' · Changes are saved when you choose Save board':' · Read only');render();
        };
        const saveBoard=async()=>{
            if(!active||!editable||!board)return;
            if(!title.value.trim()||board.cards.some(card=>!card.text.trim())){status.textContent='A board name and nonempty card text are required.';return;}
            const payload={board_id:board.id,expected_revision:board.revision,name:title.value.trim(),cards:board.cards};const signature=JSON.stringify(payload);
            if(!attempt||attempt.signature!==signature)attempt={signature,key:'board-'+crypto.randomUUID()};
            save.disabled=true;
            try{
                const result=await host.services.call('boards','save',payload,{signal:controller.signal,idempotencyKey:attempt.key});
                if(!active||signal.aborted)return;board=structuredClone(result);dirty=false;attempt=null;status.textContent='Saved · revision '+board.revision;render();
            }catch(error){if(active&&error.name!=='AbortError'){status.textContent=error.code==='CONFLICT'?'This board changed elsewhere. Your draft is still here. Download it before reloading.':error.code+' · Outcome '+(error.details?.outcome||'unknown')+'. Keep this page to retry safely.';
                if(!root.querySelector('.mp_canvas_recovery')){const download=document.createElement('button');download.className='mp_canvas_recovery';download.textContent='Download board draft';on(download,'click',()=>{const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='canvas-draft.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});header.append(download);}
            }}finally{if(active)save.disabled=!editable;}
        };
        on(title,'input',changed);on(save,'click',saveBoard);
        on(reset,'click',async()=>{if(!dirty||await host.dialogs.confirm({title:'Unsaved board',message:'Discard unsaved board changes and load the saved revision?'}))await load(currentRoute);});
        on(form,'submit',event=>{event.preventDefault();if(!board||board.cards.length>=40){status.textContent='A board can contain up to 40 cards.';return;}board.cards.push({id:crypto.randomUUID(),text:text.value.trim(),lane:'inbox',note_id:note.value||null});text.value='';changed();render();text.focus();});
        on(document,'keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){event.preventDefault();saveBoard();}});
        const theme=value=>root.dataset.theme=value.mode;theme(host.theme.current());const unsubscribe=host.theme.subscribe(theme);
        root.dir=host.locale.current().direction;
        try{
            const result=await host.services.call('documents','list',{limit:100},{signal:controller.signal});notes=result.documents;
            if(signal.aborted)throw new DOMException('Page disposed','AbortError');
            for(const value of notes){const option=document.createElement('option');option.value=value.document_id;option.textContent=value.content.headline;note.append(option);}
            await load(route);
        }catch(error){active=false;controller.abort();unsubscribe();signal.removeEventListener('abort',abort);root.remove();throw error;}
        return {
            async updateRoute(next){currentRoute=next;if((next.query.board||'')!==(route.query.board||''))await load(next);route=next;},
            canLeave:()=>dirty?'confirm':'allow',
            dispose(){active=false;controller.abort();unsubscribe();signal.removeEventListener('abort',abort);root.remove();},
        };
    },
};
