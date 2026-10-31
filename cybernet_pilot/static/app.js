const menuButton=document.querySelector('[data-menu]');
const sidebar=document.getElementById('sidebar');
menuButton?.addEventListener('click',()=>{
  const open=sidebar.classList.toggle('open');
  menuButton.setAttribute('aria-expanded',String(open));
});
document.addEventListener('click',event=>{
  if(sidebar?.classList.contains('open')&&!sidebar.contains(event.target)&&!menuButton.contains(event.target)){
    sidebar.classList.remove('open');menuButton.setAttribute('aria-expanded','false');
  }
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&sidebar?.classList.contains('open')){
    sidebar.classList.remove('open');menuButton.setAttribute('aria-expanded','false');menuButton.focus();
  }
});
async function refreshLiveRegions(){
  if(document.hidden||!document.querySelector('[data-live-region]'))return;
  try{
    const response=await fetch(location.href,{cache:'no-store',headers:{'X-Live-Update':'1'}});
    if(!response.ok)return;
    const fresh=new DOMParser().parseFromString(await response.text(),'text/html');
    const current=document.querySelectorAll('[data-live-region]');
    const next=fresh.querySelectorAll('[data-live-region]');
    if(current.length!==next.length)return;
    current.forEach((region,index)=>{
      if(region.contains(document.activeElement))return;
      const scroll=region.querySelector('.table-scroll');
      const top=scroll?.scrollTop??0,left=scroll?.scrollLeft??0;
      region.innerHTML=next[index].innerHTML;
      const restored=region.querySelector('.table-scroll');
      if(restored){restored.scrollTop=top;restored.scrollLeft=left;}
    });
  }catch(_error){/* The next interval retries; form input stays untouched. */}
}
setInterval(refreshLiveRegions,10000);
