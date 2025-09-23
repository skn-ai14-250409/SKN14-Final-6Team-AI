(function(){
  async function fetchOptions(){
    const res = await fetch('/auth/memberships');
    return await res.json();
  }
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }
  
  async function selectMembership(name){

    const localToken = localStorage.getItem('access_token');
    const cookieToken = getCookie('access_token');
    const userIdCookie = getCookie('user_id');
    const token = localToken || cookieToken;
    
    console.log('localStorage token:', localToken ? 'exists' : 'not found');
    console.log('Cookie token:', cookieToken ? 'exists' : 'not found');
    console.log('User ID cookie:', userIdCookie ? 'exists' : 'not found');
    console.log('Final token:', token ? 'exists' : 'not found');
    
    if (!token && !userIdCookie) {
      console.log('No authentication found - returning auth error');
      return { 
        success: false, 
        isAuthError: true,
        detail: '회원만 사용할 수 있는 기능입니다.' 
      };
    }
    
    const res = await fetch('/auth/membership/select', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      credentials: 'include',
      body: JSON.stringify({ membership: name })
    });
    
    if (res.status === 401) {
      localStorage.removeItem('access_token'); 
      return { 
        success: false, 
        isAuthError: true,
        detail: '회원만 사용할 수 있는 기능입니다.' 
      };
    }
    
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
      const feeText = fee === 0 ? '기본' : `월 ${fee.toLocaleString('ko-KR')}원`;
      const features = (opt.features||[]).map(f=>`<li class="text-sm text-gray-600">• ${escapeHtml(f)}</li>`).join('');
      card.innerHTML = `
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-gray-800">${escapeHtml(opt.membership_name)}</h3>
          <span class="text-sm text-gray-500">${feeText}</span>
        </div>
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
        console.log('selectMembership 결과:', result); 
        if (result && result.success){
          if (result.message) {

            setFeedback(result.message, 'info');
          } else {

            let countdown = 5;
            const box = document.getElementById('feedback');

            box.className = 'mt-6 p-3 rounded';
            box.classList.remove('hidden');
            box.innerHTML = `
              <div class="text-center">
                <div class="mb-4 text-gray-700 text-lg font-semibold">멤버십이 적용되었습니다. ${countdown}초 후 챗봇으로 이동합니다.</div>
                <div class="flex justify-center">
                  <div class="delivery-scene">
                    <div class="delivery-farmer farmer">
                      <div class="hat"></div>
                      <div class="face">
                        <div class="eye left"></div>
                        <div class="eye right"></div>
                        <div class="mouth"></div>
                      </div>
                      <div class="body"></div>
                    </div>
                    
                    <div class="house-person">
                      <div class="house">
                        <div class="house-door"></div>
                      </div>
                      <div class="person">
                        <div class="person-head"></div>
                        <div class="person-body"></div>
                      </div>
                    </div>
                    
                    <div class="delivery-path"></div>
                    
                    <div class="delivery-carrot">
                      <div class="carrot-body"></div>
                      <div class="carrot-leaves">
                        <div class="carrot-leaf"></div>
                        <div class="carrot-leaf"></div>
                        <div class="carrot-leaf"></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            `;
            
            const countdownTimer = setInterval(() => {
              countdown--;
              if (countdown > 0) {
                const messageDiv = document.querySelector('#feedback .text-center > div:first-child');
                if (messageDiv) {
                  messageDiv.textContent = `멤버십이 적용되었습니다. ${countdown}초 후 챗봇으로 이동합니다.`;
                }
              } else {
                clearInterval(countdownTimer);
                window.location.href = '/chat';
              }
            }, 1000);
          }
        } else if (result && result.isAuthError) {

          let countdown = 5;
          const updateMessage = () => {
            setFeedback(result.detail + ` ${countdown}초 후에 로그인 페이지로 넘어갑니다.`, 'error');
          };
          
          updateMessage(); 
          
          const countdownTimer = setInterval(() => {
            countdown--;
            if (countdown > 0) {

              const messageDiv = document.querySelector('#feedback .text-center > div:first-child');
              if (messageDiv) {
                messageDiv.textContent = result.detail + ` ${countdown}초 후에 로그인 페이지로 넘어갑니다.`;
              }
            } else {
              clearInterval(countdownTimer);
              window.location.href = '/login';
            }
          }, 1000);
        } else {
          setFeedback(result?.detail||'적용에 실패했습니다.', 'error');
        }
      }catch(err){ 
        console.error('멤버십 선택 오류:', err); 
        setFeedback('네트워크 오류가 발생했습니다.', 'error'); 
      }
    }, { once:false });
  }
  function escapeHtml(s){ const d=document.createElement('div'); d.textContent=String(s||''); return d.innerHTML; }
  function setFeedback(msg, type){
    const box = document.getElementById('feedback');
    box.className='mt-6 p-3 rounded hidden';
    box.innerHTML='';
    if (!msg) return;
    
    if (type === 'error' && msg.includes('회원만 사용할 수 있는 기능입니다')) {
      box.innerHTML = `
        <div class="text-center">
          <div class="mb-4 text-gray-700">${msg}</div>
          <div class="flex justify-center">
            <div class="carrot-scene">
              <div class="farmer">
                <div class="hat"></div>
                <div class="face">
                  <div class="eye left"></div>
                  <div class="eye right"></div>
                  <div class="mouth"></div>
                </div>
                <div class="body"></div>
                <div class="arm left-arm"></div>
                <div class="arm right-arm">
                  <div class="pickaxe">⛏️</div>
                </div>
                <div class="leg left-leg"></div>
                <div class="leg right-leg"></div>
              </div>
              <div class="ground"></div>
              <div class="carrots">
                <div class="carrot-plant" id="plant-1">
                  <div class="carrot-body">🥕</div>
                  <div class="carrot-leaves">🌿</div>
                </div>
                <div class="carrot-plant" id="plant-2">
                  <div class="carrot-body">🥕</div>
                  <div class="carrot-leaves">🌿</div>
                </div>
                <div class="carrot-plant" id="plant-3">
                  <div class="carrot-body">🥕</div>
                  <div class="carrot-leaves">🌿</div>
                </div>
                <div class="carrot-plant" id="plant-4">
                  <div class="carrot-body">🥕</div>
                  <div class="carrot-leaves">🌿</div>
                </div>
                <div class="carrot-plant" id="plant-5">
                  <div class="carrot-body">🥕</div>
                  <div class="carrot-leaves">🌿</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
      
      for (let i = 1; i <= 5; i++) {
        setTimeout(() => {
          const plant = document.getElementById(`plant-${i}`);
          if (plant) plant.classList.add('pulled');
        }, i * 1000);
      }
    } else {
      box.textContent = msg;
    }
    
    box.classList.remove('hidden');

    if (type === 'error' && msg.includes('회원만 사용할 수 있는 기능입니다')) {

    } else if (type==='success') {
      box.classList.add('bg-green-50','text-green-700','border','border-green-200');
    } else if (type==='error') {
      box.classList.add('bg-red-50','text-red-700','border','border-red-200');
    } else {
      box.classList.add('bg-blue-50','text-blue-700','border','border-blue-200');
    }
  }
  async function init(){
    try{ const data = await fetchOptions(); renderOptions(data.options||[]); }
    catch(err){ setFeedback('옵션을 불러오지 못했습니다.', 'error'); }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
