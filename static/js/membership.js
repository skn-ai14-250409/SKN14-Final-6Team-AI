(function(){
  async function fetchOptions(){
    const res = await fetch('/auth/memberships');
    return await res.json();
  }
  async function selectMembership(name){
    const token = localStorage.getItem('access_token');
    const res = await fetch('/auth/membership/select', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      credentials: 'include',
      body: JSON.stringify({ membership: name })
    });
    return await res.json();
  }
  function renderOptions(list){
    const wrap = document.getElementById('membershipList');
    wrap.innerHTML = '';
    list.forEach(opt => {
      const card = document.createElement('div');
      card.className = 'bg-white rounded-xl p-5 shadow flex flex-col h-full';
      const rate = Math.round((opt.discount_rate||0)*100);
      const thr = Math.round(opt.free_shipping_threshold||0);
      const fee = Math.round(opt.monthly_fee||0);
      const features = (opt.features||[]).map(f=>`<li class="text-sm text-gray-600">• ${escapeHtml(f)}</li>`).join('');
      card.innerHTML = `
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-gray-800">${escapeHtml(opt.membership_name)}</h3>
          <span class="text-sm text-gray-500">월 ${fee.toLocaleString('ko-KR')}원</span>
        </div>
        <div class="text-sm text-gray-700 mb-2">할인: ${rate}% · 무료배송 기준: ${thr===0?'항상 무료':thr.toLocaleString('ko-KR')+'원 이상'}</div>
        <ul class="mb-4">${features}</ul>
        <button class="mt-auto w-full bg-green-600 hover:bg-green-700 text-white rounded-lg py-2 select-btn" data-name="${escapeHtml(opt.membership_name)}">선택</button>
      `;
      wrap.appendChild(card);
    });
    wrap.addEventListener('click', async (e)=>{
      const btn = e.target.closest('.select-btn');
      if (!btn) return;
      try{
        setFeedback('선택을 적용 중입니다...', 'info');
        const result = await selectMembership(btn.dataset.name);
        if (result && result.success){
          setFeedback('멤버십이 적용되었습니다. 장바구니 혜택이 반영됩니다.', 'success');
        }else{
          setFeedback(result?.detail||'적용에 실패했습니다.', 'error');
        }
      }catch(err){ setFeedback('네트워크 오류가 발생했습니다.', 'error'); }
    }, { once:false });
  }
  function escapeHtml(s){ const d=document.createElement('div'); d.textContent=String(s||''); return d.innerHTML; }
  function setFeedback(msg, type){
    const box = document.getElementById('feedback');
    box.className='mt-6 p-3 rounded hidden';
    box.textContent='';
    if (!msg) return;
    box.textContent = msg;
    box.classList.remove('hidden');
    if (type==='success') box.classList.add('bg-green-50','text-green-700','border','border-green-200');
    else if (type==='error') box.classList.add('bg-red-50','text-red-700','border','border-red-200');
    else box.classList.add('bg-blue-50','text-blue-700','border','border-blue-200');
  }
  async function init(){
    try{ const data = await fetchOptions(); renderOptions(data.options||[]); }
    catch(err){ setFeedback('옵션을 불러오지 못했습니다.', 'error'); }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
