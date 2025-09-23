let currentActiveMenu = 'orders';
let MYPAGE_USER_ID = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('마이페이지(탭) 초기화');
    initializeMenuEvents();
    resolveCurrentUser().then(uid => {
        MYPAGE_USER_ID = uid;
        try { updateWelcomeName(); } catch(_){}
        
    });
});

function initializeMenuEvents() {

    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(item => {
        item.addEventListener('click', function() {

            this.style.transform = 'translateX(8px) scale(0.98)';
            setTimeout(() => {
                this.style.transform = 'translateX(4px)';
            }, 150);
        });
    });
}

function showContent(contentType) {
    console.log(`메뉴 전환: ${contentType}`);
    
    const allSections = document.querySelectorAll('.content-section');
    allSections.forEach(section => {
        section.classList.add('hidden');
        section.classList.remove('active');
    });
    
    const targetSection = document.getElementById(`content-${contentType}`);
    if (targetSection) {
        targetSection.classList.remove('hidden');
        targetSection.classList.add('active');

        targetSection.style.opacity = '0';
        targetSection.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            targetSection.style.transition = 'all 0.3s ease';
            targetSection.style.opacity = '1';
            targetSection.style.transform = 'translateY(0)';
        }, 50);
    }
    
    if (contentType === 'profile') loadUserProfile();
    if (contentType === 'orders') loadOrders();
    if (contentType === 'delivery') loadDeliveries();
    if (contentType === 'chat') loadChatHistory();
    if (contentType === 'recipes') { try { renderSavedRecipes(); } catch(_) {} }

    setActiveMenu(contentType);
    currentActiveMenu = contentType;
}

function setActiveMenu(menuType) {

    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(item => {
        item.classList.remove('bg-green-600', 'bg-opacity-30');
        item.style.backgroundColor = '';
    });
    
    const activeMenuItem = document.querySelector(`[data-menu="${menuType}"]`);
    if (activeMenuItem) {
        activeMenuItem.style.backgroundColor = 'rgba(34, 197, 94, 0.3)';
        activeMenuItem.classList.add('bg-green-600', 'bg-opacity-30');
    }
}

function editProfile() {
    console.log('회원정보 수정 버튼이 클릭되었습니다.');
    showContent('profile');
}

function loadUserProfile() {
    console.log('사용자 개인정보 로드');
    
    fetch('/api/profile/get')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                populateProfileForm(data.user);
            } else {
                showNotification('사용자 정보를 불러올 수 없습니다.', 'error');
            }
        })
        .catch(error => {
            console.error('사용자 정보 로드 실패:', error);
            showNotification('사용자 정보 로드 중 오류가 발생했습니다.', 'error');
        });
}

function populateProfileForm(userData) {
    console.log('프로필 폼에 데이터 채우기', userData);

    const fields = {
        'profileUserId': userData.user_id,
        'profileName': userData.name,
        'profileEmail': userData.email,
        'profilePhone': userData.phone_num,
        'profileBirthDate': userData.birth_date,
        'profileAge': userData.age,
        'profileAddress': userData.address,
        'profilePostNum': userData.post_num,
        'profileHouseHold': userData.house_hold,
        'profileAllergy': userData.allergy,
        'profileUnfavorite': userData.unfavorite
    };
    
    Object.keys(fields).forEach(fieldId => {
        const element = document.getElementById(fieldId);
        if (element && fields[fieldId] !== null && fields[fieldId] !== undefined) {
            element.value = fields[fieldId];
        }
    });

    const membershipElement = document.getElementById('profileMembership');
    if (membershipElement && userData.membership) {
        const membershipDisplayNames = {
            'basic': 'Basic - 기본 회원',
            'premium': 'Premium - 프리미엄 회원 (월 9,900원)',
            'gold': 'Gold - 골드 회원 (월 19,900원)'
        };
        membershipElement.value = membershipDisplayNames[userData.membership] || userData.membership;
    }
    
    if (userData.gender) {
        const genderRadio = document.querySelector(`input[name="gender"][value="${userData.gender}"]`);
        if (genderRadio) {
            genderRadio.checked = true;
        }
    }

    const veganCheckbox = document.getElementById('profileVegan');
    if (veganCheckbox) {
        veganCheckbox.checked = userData.vegan === 1;
    }
}

function saveProfile() {
    console.log('개인정보 저장 시작');

    const formData = {
        name: document.getElementById('profileName').value,
        email: document.getElementById('profileEmail').value,
        phone_num: document.getElementById('profilePhone').value,
        birth_date: document.getElementById('profileBirthDate').value,
        address: document.getElementById('profileAddress').value,
        post_num: document.getElementById('profilePostNum').value,
        age: document.getElementById('profileAge').value,
        gender: document.querySelector('input[name="gender"]:checked')?.value,
        house_hold: document.getElementById('profileHouseHold').value,
        vegan: document.getElementById('profileVegan').checked ? 1 : 0,
        allergy: document.getElementById('profileAllergy').value,
        unfavorite: document.getElementById('profileUnfavorite').value
    };

    if (!formData.name || !formData.email) {
        showNotification('이름과 이메일은 필수 입력 항목입니다.', 'error');
        return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
        showNotification('올바른 이메일 형식을 입력해주세요.', 'error');
        return;
    }

    fetch('/api/profile/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('개인정보가 성공적으로 저장되었습니다.', 'info');

            showContent('orders');
        } else {
            showNotification(data.message || '저장 중 오류가 발생했습니다.', 'error');
        }
    })
    .catch(error => {
        console.error('개인정보 저장 실패:', error);
        showNotification('저장 중 오류가 발생했습니다.', 'error');
    });
}

function cancelProfileEdit() {
    console.log('개인정보 수정 취소');
    showContent('orders');
}

function resolveCurrentUser(){
  return fetch('/auth/status', { credentials:'include' })
    .then(r=>r.json())
    .then(d=> d && d.user_id ? d.user_id : (JSON.parse(localStorage.getItem('user_info')||'{}').user_id || 'anonymous'))
    .catch(()=> 'anonymous');
}

function updateWelcomeName(){
  const el = document.querySelector('.welcome-name');
  const sidebarEl = document.querySelector('.sidebar-user-name');

  fetch('/api/profile/get', { credentials:'include' })
    .then(r=>r.json())
    .then(d=>{
      if (d && d.success && d.user && d.user.name) {
        if (el) el.textContent = d.user.name;
        if (sidebarEl) sidebarEl.textContent = d.user.name;
      }
    });
}

function updateUserName(name) {
    const userNameElements = document.querySelectorAll('.user-name, .welcome-name');
    userNameElements.forEach(element => {
        element.textContent = `${name} 님`;
    });
}

async function loadOrders(){
  try{
    const uid = MYPAGE_USER_ID || (await resolveCurrentUser());
    const res = await fetch('/api/orders/history', {
      method:'POST', headers:{ 'Content-Type':'application/json' }, credentials:'include',
      body: JSON.stringify({ user_id: uid, limit: 20 })
    });
    const data = await res.json();
    const orders = Array.isArray(data.orders) ? data.orders : [];
    const list = document.getElementById('ordersList');
    if (!list) return;
    if (orders.length === 0){ list.innerHTML = '<div class="text-gray-500">최근 주문 내역이 없습니다.</div>'; return; }

    list.innerHTML = orders.map(o=>renderOrderCard(o)).join('');
  }catch(e){ console.error('loadOrders error:', e); }
}

function renderOrderCard(o){
  const code = escapeHtml(String(o.order_code));
  const date = escapeHtml(String(o.order_date||''));
  const status = String(o.order_status||'').toLowerCase();
  const total = formatKRW(o.total_price||0);
  const badge = status.includes('deliver')
    ? '<span class="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-medium">배송완료</span>'
    : '<span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">처리중</span>';
  return `
    <div class="bg-gray-50 rounded-lg p-6 border border-gray-200">
      <div class="flex justify-between items-start mb-4">
        <div>
          <h3 class="font-semibold text-lg text-gray-800">주문번호: ${code}</h3>
          <p class="text-gray-600 text-sm">${date}</p>
        </div>
        ${badge}
      </div>
      <div class="border-t mt-4 pt-4 flex justify-between items-center">
        <span class="font-semibold text-lg">총 금액</span>
        <span class="font-bold text-lg text-green-600">${total}원</span>
      </div>
      <div class="mt-3 text-right">
        <button class="order-detail-btn px-3 py-1 text-sm border rounded hover:bg-gray-100" data-code="${code}">상세 보기</button>
      </div>
      <div class="order-detail-panel mt-3 hidden"></div>
    </div>`;
}

async function loadDeliveries(){
  try{
    const uid = MYPAGE_USER_ID || (await resolveCurrentUser());
    const res = await fetch('/api/orders/history', {
      method:'POST', headers:{ 'Content-Type':'application/json' }, credentials:'include',
      body: JSON.stringify({ user_id: uid, limit: 20 })
    });
    const data = await res.json();
    const orders = (data.orders||[]).filter(o=> String(o.order_status||'').toLowerCase().includes('deliver') || String(o.order_status||'').toLowerCase()==='confirmed');
    const list = document.getElementById('deliveryList');
    if (!list) return;
    if (orders.length === 0){ list.innerHTML = '<div class="text-gray-500">표시할 배송 내역이 없습니다.</div>'; return; }
    list.innerHTML = orders.map(o=>renderDeliveryCard(o)).join('');
  }catch(e){ console.error('loadDeliveries error:', e); }
}

function renderDeliveryCard(o){
  const code = escapeHtml(String(o.order_code));
  const status = String(o.order_status||'');
  const badge = status.toLowerCase().includes('deliver')
    ? '<span class="bg-green-500 text-white px-3 py-1 rounded-full text-sm font-medium"><i class="fas fa-check mr-1"></i>배송완료</span>'
    : '<span class="bg-blue-500 text-white px-3 py-1 rounded-full text-sm font-medium"><i class="fas fa-truck mr-1"></i>배송중</span>';
  const date = escapeHtml(String(o.order_date||''));
  return `
  <div class="bg-gradient-to-r from-green-50 to-blue-50 rounded-lg p-6 border border-green-200">
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-semibold text-lg text-gray-800">${code}</h3>
      ${badge}
    </div>
    <p class="text-gray-600 text-sm">주문 일시: ${date}</p>
    <div class="bg-white rounded-lg p-4 mt-4">
      <p class="text-sm text-gray-700"><strong>배송업체:</strong> Qook 배송</p>
      <p class="text-sm text-gray-700"><strong>운송장번호:</strong> - </p>
      <p class="text-sm text-gray-700"><strong>예상 도착:</strong> - </p>
    </div>
  </div>`;
}

async function loadChatHistory(){
  try{
    const uid = MYPAGE_USER_ID || (await resolveCurrentUser());
    const res = await fetch('/api/orders/chat-history', {
      method:'POST', headers:{ 'Content-Type':'application/json' }, credentials:'include',
      body: JSON.stringify({ user_id: uid, limit: 200 })
    });
    const data = await res.json();
    const messages = Array.isArray(data.messages) ? data.messages : [];
    const wrap = document.getElementById('chatHistory');
    if (!wrap) return;
    if (messages.length===0){ wrap.innerHTML = '<div class="text-gray-500">최근 대화가 없습니다.</div>'; return; }
    const sessions = {};
    messages.forEach(m=>{ const sid = m.log_id || 'unknown'; (sessions[sid]||=([])).push(m); });
    const sessionEntries = Object.entries(sessions).map(([sid, items])=>{
      const sorted = items.slice().sort((a,b)=> new Date(a.time).getTime() - new Date(b.time).getTime());
      const firstTs = new Date(sorted[0]?.time || Date.now());
      return { sid, messages: sorted, firstTs };
    }).sort((a,b)=> b.firstTs.getTime() - a.firstTs.getTime());

    const totalSessions = sessionEntries.length;
    const cardsHtml = sessionEntries.map((session, idx)=>{ 
      const summary = formatSessionHeader(session.firstTs); 
      const detail = session.messages.map(renderChatRow).join('');
      const sessionLabel = `세션 ${totalSessions - idx}`;
      return `
        <div class="chat-session-card bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div class="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
            <div>
              <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">${escapeHtml(sessionLabel)}</p>
              <p class="text-base font-semibold text-gray-800 mt-1">${escapeHtml(summary)}</p>
            </div>
            <button type="button" class="chat-detail-toggle px-3 py-1.5 text-sm font-semibold text-green-600 bg-white border border-green-200 rounded-lg shadow-sm hover:bg-green-50 transition" data-sid="${escapeHtml(session.sid)}">상세 보기</button>
          </div>
          <div class="chat-session-detail hidden px-4 py-4 bg-gradient-to-br from-gray-50 to-white">
            <div class="space-y-3">${detail}</div>
          </div>
        </div>`;
    }).join('');

    wrap.innerHTML = `<div class="chat-history-session-list space-y-4">${cardsHtml}</div>`;  
  }catch(e){ console.error('loadChatHistory error:', e); }
}

function renderChatRow(m){
  const isUser = m.role === 'user';
  const rawText = m.text || '';
  const text = isUser ? formatUserMessage(rawText) : renderBotMarkdown(rawText);  
  const timeLabel = formatChatTimestamp(m.time);
  const align = isUser ? 'justify-end' : 'justify-start';
  const bubbleClass = isUser ? 'bg-green-600 text-white' : 'bg-white text-gray-800';
  const timeClass = isUser ? 'text-right text-white opacity-80 font-medium' : 'text-left text-gray-600 font-medium';  
  const avatar = isUser
    ? '<div class="w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center ml-3"><i class="fas fa-user"></i></div>'
    : '<div class="w-8 h-8 rounded-full bg-gray-200 text-green-600 flex items-center justify-center mr-3"><i class="fas fa-robot"></i></div>';

  return `
    <div class="flex ${align} items-end">
      ${isUser ? '' : avatar}
      <div class="max-w-[70%]">
        <div class="${bubbleClass} rounded-2xl px-4 py-2 shadow-sm leading-relaxed">
          ${isUser ? '' : '<span class="block text-sm font-semibold text-green-900 mb-1">Qook</span>'}
          ${text}
        </div>
        <div class="text-xs ${timeClass} mt-1">${escapeHtml(timeLabel)}</div>
      </div>
      ${isUser ? avatar : ''}
    </div>`;
}

function formatKRW(n){ const v = Math.round(Number(n)||0); return v.toLocaleString('ko-KR'); }
function escapeHtml(s){ const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
function formatSessionHeader(date){
  try {  
    const dt = new Date(date);
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, '0');
    const d = String(dt.getDate()).padStart(2, '0');
    const minutes = String(dt.getMinutes()).padStart(2, '0');
    let hour = dt.getHours();
    const period = hour < 12 ? '오전' : '오후';
    hour = hour % 12 || 12;
    const hourLabel = String(hour).padStart(2, '0');
    return `${y}. ${m}.${d} ${period} ${hourLabel}:${minutes}`;
  } catch (_) {
    return String(date || '최근 대화');
  }
}
function formatChatTimestamp(value){
  try {
    return new Date(value).toLocaleTimeString('ko-KR', { hour:'2-digit', minute:'2-digit' });
  } catch (_) {
    return String(value || '');
  }
}

function formatUserMessage(text){  
  return escapeHtml(String(text||'')).replace(/\n/g, '<br>');
}

function renderBotMarkdown(text){  
  const fallback = escapeHtml(String(text||'')).replace(/\n/g, '<br>');
  try {
    if (window.QMarkdown && typeof window.QMarkdown.render === 'function'){
      return QMarkdown.render(text);
    }
    return fallback;
  } catch (err){
    console.warn('markdown render 실패', err);
    return fallback;
  }
}

document.addEventListener('click', async (e)=>{
  const btn = e.target.closest('.order-detail-btn');
  if (btn){
    const code = btn.dataset.code; const panel = btn.closest('.bg-gray-50')?.querySelector('.order-detail-panel');
    if (!code || !panel) return;
    try{
      const uid = MYPAGE_USER_ID || (await resolveCurrentUser());
      const res = await fetch('/api/orders/details', { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({ user_id: uid, order_code: String(code) }) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail||'상세 조회 실패');
      panel.innerHTML = renderOrderDetails(data);
      panel.classList.toggle('hidden');
    }catch(err){ console.error('order details error:', err); }
  }
  const chatToggle = e.target.closest('.chat-detail-toggle');
  if (chatToggle){  
    const card = chatToggle.closest('.chat-session-card');
    const detail = card?.querySelector('.chat-session-detail');
    if (!detail) return;
    const willOpen = detail.classList.contains('hidden');
    detail.classList.toggle('hidden');
    chatToggle.textContent = willOpen ? '접기' : '상세 보기';
    if (willOpen){
      detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }
});

function renderOrderDetails(d){
  const items = (d.items||[]).map((it, idx)=>{
    const name = escapeHtml(it.product||it.name||'');
    const qty = Number(it.quantity||it.qty||0);
    const lineTotal = Number(it.price||it.unit_price||0);
    const line = Number(lineTotal||0).toLocaleString('ko-KR');
    return `<div class=\"flex justify-between text-sm\"><div>${idx+1}. ${name} × ${qty}</div><div>${line}원</div></div>`;
  }).join('');
  const subtotal = Number(d.subtotal||0).toLocaleString('ko-KR');
  const discount = Number(d.discount_amount||0).toLocaleString('ko-KR');
  const shipping = Number(d.shipping_fee||0).toLocaleString('ko-KR');
  const total = Number(d.total_price||0).toLocaleString('ko-KR');
  return `
    <div class=\"rounded border p-3 bg-white\"> 
      <div class=\"space-y-1 mb-2\">${items||'<div class=\"text-gray-500 text-sm\">항목 없음</div>'}</div>
      <div class=\"border-t pt-2 text-sm\">
        <div class=\"flex justify-between\"><span>상품 합계</span><span>${subtotal}원</span></div>
        <div class=\"flex justify-between\"><span>할인</span><span class=\"text-red-600\">- ${discount}원</span></div>
        <div class=\"flex justify-between\"><span>배송비</span><span>${shipping}원</span></div>
        <div class=\"flex justify-between font-semibold\"><span>총 결제금액</span><span>${total}원</span></div>
      </div>
    </div>`;
}

function renderSavedRecipes(){
  const grid = document.querySelector('#content-recipes .grid');
  if (!grid) return;
  try{
    const uid = JSON.parse(localStorage.getItem('user_info')||'{}').user_id || 'guest';
    const local = JSON.parse(localStorage.getItem(`favorite_recipes_${uid}`)||'[]');
    fetch(`/api/recipes/favorites?user_id=${encodeURIComponent(uid)}`, { credentials:'include' })
      .then(r=>r.json()).then(async data=>{
        let serverItems = (data && data.items) ? data.items : [];
        if ((!serverItems || serverItems.length===0) && Array.isArray(local) && local.length>0){
          try{
            await fetch('/api/recipes/favorites/bulk-sync',{
              method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
              body: JSON.stringify({ user_id: uid, items: local.map(x=>({ user_id:uid, recipe_url:x.url, recipe_title:x.title, snippet:x.description||'' })) })
            });
            const r2 = await fetch(`/api/recipes/favorites?user_id=${encodeURIComponent(uid)}`, { credentials:'include' });
            const d2 = await r2.json();
            serverItems = d2.items||[];
          }catch(e){ console.error('bulk-sync error', e); }
        }
        if (!serverItems || serverItems.length===0){ grid.innerHTML = '<div class="text-gray-500">저장한 레시피가 없습니다.</div>'; return; }
        grid.innerHTML = serverItems.map(r=>{
          const title = escapeHtml(r.recipe_title||'레시피');
          const desc = escapeHtml(r.snippet||'');
          const url = r.recipe_url||'#';
          return `
          <div class=\"bg-white rounded-lg shadow-md overflow-hidden border border-gray-200\"> 
            <div class=\"h-48 bg-gradient-to-br from-green-100 to-blue-100 flex items-center justify-center\">
              <i class=\"fas fa-utensils text-6xl text-green-400\"></i>
            </div>
            <div class=\"p-6\">
              <h3 class=\"font-semibold text-xl text-gray-800 mb-2\">${title}</h3>
              <p class=\"text-gray-600 text-sm mb-4\">${desc}</p>
              <div class=\"mt-4 flex items-center justify-between\">
                <a class=\"inline-block bg-green-500 text-white py-2 px-4 rounded-lg hover:bg-green-600 transition duration-200\" target=\"_blank\" href=\"${url}\">레시피 보기</a>
                <button class=\"saved-recipe-ingredients-btn border px-3 py-2 rounded hover:bg-gray-50\" data-title=\"${title}\" data-desc=\"${desc}\" data-url=\"${url}\">재료 추천받기</button>
              </div>
            </div>
          </div>`;
        }).join('');

        try { addSavedRecipeRemoveButtons(); } catch(_){ }
      }).catch(()=>{
        if (!local || local.length===0){ grid.innerHTML = '<div class="text-gray-500">저장한 레시피가 없습니다.</div>'; return; }
        grid.innerHTML = local.map(r=>{
          const title = escapeHtml(r.title||'레시피');
          const desc = escapeHtml(r.description||'');
          const url = r.url||'#';
          return `
          <div class=\"bg-white rounded-lg shadow-md overflow-hidden border border-gray-200\"> 
            <div class=\"h-48 bg-gradient-to-br from-green-100 to-blue-100 flex items-center justify-center\">
              <i class=\"fas fa-utensils text-6xl text-green-400\"></i>
            </div>
            <div class=\"p-6\">
              <h3 class=\"font-semibold text-xl text-gray-800 mb-2\">${title}</h3>
              <p class=\"text-gray-600 text-sm mb-4\">${desc}</p>
              <div class=\"mt-4 flex items-center justify-between\">
                <a class=\"inline-block bg-green-500 text-white py-2 px-4 rounded-lg hover:bg-green-600 transition duration-200\" target=\"_blank\" href=\"${url}\">레시피 보기</a>
                <button class=\"saved-recipe-ingredients-btn border px-3 py-2 rounded hover:bg-gray-50\" data-title=\"${title}\" data-desc=\"${desc}\" data-url=\"${url}\">재료 추천받기</button>
              </div>
            </div>
          </div>`;
        }).join('');

        try { addSavedRecipeRemoveButtons(); } catch(_){ }
      });
  }catch(e){ console.error('renderSavedRecipes error:', e); }
}

document.addEventListener('click', (e)=>{
  const btn = e.target.closest('.saved-recipe-ingredients-btn');
  if (!btn) return;
  const title = btn.dataset.title || '';
  const desc = btn.dataset.desc || '';
  const url = btn.dataset.url || '';
  const msg = `선택된 레시피: "${title}"
레시피 설명: ${desc}
URL: ${url}

이 레시피에 필요한 재료들을 우리 쇼핑몰에서 구매 가능한 상품으로 추천해주세요.`;
  try{
    const uid = JSON.parse(localStorage.getItem('user_info')||'{}').user_id || 'guest';
    localStorage.setItem(`chat_pending_message_${uid}`, msg);
  }catch(_){ }
  if (typeof navigateToPage === 'function') navigateToPage('/chat'); else window.location.href = '/chat';
});


function addSavedRecipeRemoveButtons(){

  const grid = document.querySelector('#content-recipes .grid');
  if (!grid) return;
  const cards = grid.querySelectorAll('.bg-white.rounded-lg.shadow-md');
  cards.forEach(card => {
    const cardBody = card.querySelector('.p-6');
    const actions = cardBody ? cardBody.querySelector('.mt-4.flex.items-center.justify-between') : null;
    if (!cardBody || !actions) return;

    const oldInActions = actions.querySelector('.saved-recipe-remove-btn');
    if (oldInActions) oldInActions.remove();

    const titleEl = cardBody.querySelector('h3');
    const descEl = cardBody.querySelector('p.text-gray-600');
    const anchor = actions.querySelector('a[target="_blank"]');
    const url = anchor ? anchor.getAttribute('href') : '';
    const title = titleEl ? titleEl.textContent : '';

    let toolbar = cardBody.querySelector('.saved-recipe-toolbar');
    if (!toolbar){
      toolbar = document.createElement('div');
      toolbar.className = 'saved-recipe-toolbar flex items-center justify-end mb-2';
      if (descEl && descEl.parentNode === cardBody){
        cardBody.insertBefore(toolbar, actions);
      } else {
        cardBody.insertBefore(toolbar, actions);
      }
    }

    if (!toolbar.querySelector('.saved-recipe-remove-btn')){
      const btn = document.createElement('button');
      btn.className = 'saved-recipe-remove-btn border px-3 py-1 rounded hover:bg-gray-50 text-xs';
      btn.title = '즐겨찾기 삭제';
      btn.setAttribute('data-url', url);
      btn.setAttribute('data-title', title);
      btn.innerHTML = '<i class="fas fa-trash-alt"></i> 삭제';
      toolbar.appendChild(btn);
    }
  });
}

function normalizeRecipeEntry(entry){ 
  if (!entry) return { url: '', title: '' };
  const url = (entry.url || entry.recipe_url || '').trim();
  const title = (entry.title || entry.recipe_title || '').trim();
  return { url, title };
}

document.addEventListener('click', async (e)=>{
  const btn = e.target.closest('.saved-recipe-remove-btn');
  if (!btn) return;
  const url = btn.dataset.url || '';
  const title = btn.dataset.title || '';
  try{
    const uid = MYPAGE_USER_ID || (await resolveCurrentUser());
    await fetch('/api/recipes/favorites', {
      method:'DELETE', headers:{ 'Content-Type':'application/json' }, credentials:'include',
      body: JSON.stringify({ user_id: uid, recipe_url: url })
    });

    const favoritesKey = `favorite_recipes_${uid}`;
    try {
      const localFavorites = JSON.parse(localStorage.getItem(favoritesKey) || '[]');
      const updatedFavorites = localFavorites.filter(item => {
        const normalized = normalizeRecipeEntry(item);
        const matchesUrl = normalized.url && url ? normalized.url === url : false;
        const matchesTitle = normalized.title && title ? normalized.title === title : false;
        return !(matchesUrl || matchesTitle);
      });
      localStorage.setItem(favoritesKey, JSON.stringify(updatedFavorites));
    } catch(localErr) {
      console.error('로컬스토리지 업데이트 실패:', localErr);
    }

    const card = btn.closest('.bg-white.rounded-lg');
    if (card) card.remove();

    if (!gridHasRecipeCards()) {  
      const grid = document.querySelector('#content-recipes .grid');
      if (grid) grid.innerHTML = '<div class="text-gray-500">저장한 레시피가 없습니다.</div>';
    }

    try {
      if (window.chatBot && typeof window.chatBot.renderFavorites === 'function') {
        window.chatBot.renderFavorites();
      }
    } catch(syncErr) {
      console.log('챗봇 동기화 실패:', syncErr);
    }

    showNotification(`"${title}"을(를) 즐겨찾기에서 제거했습니다.`, 'info');
  }catch(err){ console.error('remove favorite on mypage error', err); showNotification('삭제 중 오류가 발생했습니다.', 'error'); }
});


function showNotification(message, type = 'info') {

    const existingNotification = document.querySelector('.notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'info' ? '#10b981' : '#ef4444'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
        font-weight: 500;
    `;
    
    if (!document.querySelector('#notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 300);
    }, 3000);
}

function smoothPageTransition(url) {
    document.body.style.opacity = '0.5';
    setTimeout(() => {
        window.location.href = url;
    }, 150);
}


document.addEventListener('keydown', function(event) {

    if (event.key === 'Escape') {
        const notification = document.querySelector('.notification');
        if (notification) {
            notification.remove();
        }
  }
});

function gridHasRecipeCards(){ 
  const grid = document.querySelector('#content-recipes .grid');
  if (!grid) return false;
  return !!grid.querySelector('.bg-white.rounded-lg');
}


document.addEventListener('DOMContentLoaded', function() {
    const menuItems = document.querySelectorAll('.menu-item');
    
    menuItems.forEach(item => {

        item.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(8px)';
        });
        
        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0)';
        });
    });
});

console.log('마이페이지 JavaScript가 로드되었습니다.');
